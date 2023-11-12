import asyncio
import json
import nextcord as discord
from nextcord.ext import commands
import os
import re

from constantes import token, prefix

#info in json
if "bot_info.json" in os.listdir(os.path.dirname(__file__)):
    with open("bot_info.json", "r") as f:
        info = json.load(f)
else:
    info = {"smart_tweet": dict()}
    with open("bot_info.json", "w") as f:
        json.dump(info, f)

def save():
    with open("bot_info.json", "w") as f:
        json.dump(info, f)

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

def main():
    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix=prefix, help_command=None, intents = intents)

    @bot.event
    async def on_message(message):
        await bot.process_commands(message)
        await smart_tweet(message)
    
    @bot.event
    async def on_message_edit(before, after):
        await smart_tweet(after)

    @bot.event
    async def on_message_delete(message):
        await smart_tweet(message, delete=True)
    
    @bot.command(name = "ursula")
    async def ursula_command(ctx):
        ref = discord.MessageReference(channel_id = ctx.channel.id, message_id = ctx.message.id)
        e = discord.Embed(description = "Ursula von der Leyen")
        e.set_image(url = "https://cdn.discordapp.com/avatars/985833521258070057/e497e0616bfb99b2c8534bde94858bd8.png?size=1024")

        await ctx.send(embed = e, reference = ref)
    
    return bot, token

if __name__ == "__main__": #pour lancer le bot
    bot, token = main()

    loop = asyncio.get_event_loop()
    loop.create_task(bot.start(token))
    loop.run_forever()