import asyncio
import json
import nextcord as discord
from nextcord.ext import commands, tasks
import os
import re

from arrow import utcnow
from typing import Dict, List, Tuple
from constantes import token, prefix, mainAdminId
from vote import Vote, condorcet

#info in json
if "bot_info.json" in os.listdir(os.path.dirname(__file__)):
    with open("bot_info.json", "r") as f:
        info = json.load(f)
else:
    info = {"smart_tweet": dict(), "votes": dict()}
    with open("bot_info.json", "w") as f:
        json.dump(info, f)

def save():
    with open("bot_info.json", "w") as f:
        json.dump(info, f)

for categ in ("smart_tweet", "votes"):
    if categ not in info:
        info[categ] = dict()
        save()

async def dmChannelUser(user):
    """
    Récupérer le DM Channel d'un utilisateur donné
    """
    
    if user.dm_channel is None:
        await user.create_dm()
    return user.dm_channel

async def traitementRawReact(payload):
    """
    Récupérer les infos intéressantes d'une réaction discord
    """

    if payload.user_id != bot.user.id: #sinon, on est dans le cas d'une réaction en dm
        messageId = payload.message_id
        guild = bot.get_guild(payload.guild_id) if payload.guild_id else None
        try:
            user = (await guild.fetch_member(payload.user_id)) if guild else (await bot.fetch_user(payload.user_id))
        except:
            user = (await bot.fetch_user(payload.user_id))
        channel = await bot.fetch_channel(payload.channel_id)

        partEmoji = payload.emoji
        emojiHash = partEmoji.id if partEmoji.is_custom_emoji() else partEmoji.name

        return locals()
    else:
        return None

async def smart_tweet(msg: discord.Message, delete: bool = False):
    """
    Reply to messages with Twitter links whose embed fails with vxtwitter
    """
    
    msgId = msg.id
    infoSmartTweet = info["smart_tweet"]

    if delete and msgId in infoSmartTweet:
        msgRep = await msg.channel.fetch_message(infoSmartTweet[msgId])
        await msgRep.delete()
        del infoSmartTweet[msgId]

    links = re.findall("https:\/\/([\w_-]+(?:(?:\.[\w_-]+)+))([\w.,@?^=%&:\/~+#-]*[\w@?^=%&\/~+#-])", msg.content)
    links = [(x.lower(), y.lower()) for x, y in links]
    twitterLinks = ["https://" + x.replace("x.com", "twitter.com").replace("twitter.com", "vxtwitter.com") + y for x, y in links if (x.startswith("x.com") or x.startswith("twitter.com")) and "fxtwitter.com" not in x and "vxtwitter.com" not in x]

    if len(twitterLinks):
        ref = discord.MessageReference(channel_id = msg.channel.id, message_id = msgId)
        
        if msg.edited_at and "smart_tweet" in info and msgId in infoSmartTweet:
            msgRep = await msg.channel.fetch_message(infoSmartTweet[msgId])
            await msgRep.edit(content = "\n".join(twitterLinks))
        else:
            rep = await msg.channel.send("\n".join(twitterLinks), reference = ref)
            infoSmartTweet[msgId] = rep.id
    elif msg.edited_at and "smart_tweet" in info and msgId in infoSmartTweet:
        msgRep = await msg.channel.fetch_message(infoSmartTweet[msgId])
        await msgRep.edit(content = ".")

async def organise_vote(channel: discord.TextChannel, options: List[str]):
    if "votes" not in info:
        info["votes"]: Dict[str, Tuple[List[str], Dict[str, List[str]]], Tuple[int, int, int, int, int], Tuple[int, int, int, int, int], int] = dict()

    msgVote = await channel.send("**Vous pouvez voter jusqu'à mardi 21 novembre 20h**\nOptions en lice :\n" + "\n".join("- " + x for x in options) + "\n\nRéagissez avec ✅ pour voter")
    await msgVote.add_reaction("✅")

    info["votes"][str(msgVote.id)] = (options, dict(), (2023, 11, 21, 20, 0), channel.id)

    save()

async def enregistre_vote(messageId, user, emojiHash):
    if "votes" not in info or str(messageId) not in info["votes"]:
        return
    
    if emojiHash == "✅":
        options, recupVotes, _, _ = info["votes"][str(messageId)]
        vue = Vote(options, recupVotes, save)

        dmChannel = await dmChannelUser(user)
        await dmChannel.send("Choisis ton option **préférée**", view = vue)

async def depouillement(bot, msgId):
    options, votes, _, channelId = info["votes"][str(msgId)]

    channel = await bot.fetch_channel(int(channelId))
    gagnant, details = condorcet(votes, options)

    await channel.send(f"Le vote a été remporté par {gagnant} !")

    infoVote = []
    printF = lambda *args, end = "\n": infoVote.append(" ".join(str(x) for x in args) + end)
    printF("Résultats")
    
    #full rankings per voter
    names: Dict[int, str] = dict() #{user_id: user_name}
    for voterId, vote in votes.items():
        if voterId not in names:
            names[voterId] = (await bot.fetch_user(voterId)).name

        printF(f"{names[voterId]}:", ", ".join(vote))

    detailsProcessed: Dict[str, List[Tuple[str, int, int]]] = {sub: [] for sub in options}

    for (winner, loser), (pointsWinner, pointsLoser) in details.items():
        detailsProcessed[winner].append((loser, pointsWinner, pointsLoser))
    
    affiResDuels = lambda sub: "\n".join(f"a gagné le duel contre {loser} ({pointsWinner}-{pointsLoser})" for loser, pointsWinner, pointsLoser in detailsProcessed[sub])

    printF()

    for sub in options:
        isWinner = "a gagné le vote" if sub == gagnant else ""
        printF(f"{sub} {isWinner}\n" + affiResDuels(sub))
        printF()
    printF()
    
    with open(f"resultats_vote_{msgId}.txt", "w") as f:
        f.write("".join(infoVote))
    
    await channel.send("Résultats détaillés:", file = discord.File(f"resultats_vote_{msgId}.txt", filename="resultats.txt"))

async def planning(now, bot):
    datetime = (now.year, now.month, now.day, now.hour, now.minute)

    #votes
    if "votes" in info:
        for msgId, voteInfo in info["votes"].items():
            if tuple(voteInfo[2]) == datetime:
                await depouillement(bot, msgId)

def main():
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix=prefix, help_command=None, intents = intents)

    @tasks.loop(minutes = 1.0)
    async def autoplanner():
        now = utcnow().to("Europe/Brussels")
        await planning(now, bot)

    @bot.event
    async def on_ready():
        autoplanner.start()
        guild = bot.get_guild(1172592366612398111)
        print(guild.icon.url)

    @bot.event
    async def on_message(message):
        await bot.process_commands(message)
        #await smart_tweet(message)
    
    @bot.event
    async def on_message_edit(before, after):
        pass
        #await smart_tweet(after)

    @bot.event
    async def on_message_delete(message):
        #await smart_tweet(message, delete=True)
        pass

    @bot.event
    async def on_raw_reaction_add(payload):
        traitement = await traitementRawReact(payload)
        if traitement:
            messageId = traitement["messageId"]
            user = traitement["user"]
            if user.bot: return #no need to go further

            guild = traitement["guild"]
            emojiHash = traitement["emojiHash"]
            channel = traitement["channel"]
        
            await enregistre_vote(messageId, user, emojiHash)
    
    @bot.command(name = "ursula")
    async def ursula_command(ctx):
        ref = discord.MessageReference(channel_id = ctx.channel.id, message_id = ctx.message.id)
        e = discord.Embed(description = "Ursula von der Leyen")
        e.set_image(url = "https://cdn.discordapp.com/avatars/985833521258070057/e497e0616bfb99b2c8534bde94858bd8.png?size=1024")

        await ctx.send(embed = e, reference = ref)
    
    @bot.command(name = "vote")
    async def command_vote(ctx):
        if ctx.author.id == mainAdminId:
            options = ["Ouip", "Nhop", "Switch", "France Chômage", "Le Fouet"]
            await organise_vote(ctx.channel, options)

    return bot, token

if __name__ == "__main__": #pour lancer le bot
    bot, token = main()

    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(token))
    loop.run_forever()