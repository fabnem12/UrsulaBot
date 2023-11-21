from typing import Dict, List, Callable, Tuple
import nextcord as discord

UserId = str
Bulletin = List[str] #liste ordonnée

def Vote(options: List[str], votes: Dict[UserId, Bulletin], saveData: Callable[[], None]):
    """
    Definis une vue discord pour un vote
    """

    class Aux(discord.ui.View):
        def __init__(self):
            super().__init__(timeout = 3600)
            self.selectedItems: List[str] = []
        
        def showSelected(self):
            selectedItems = self.selectedItems
            return "\n".join(f"**#{i+1}** {affi}" for i, affi in enumerate(selectedItems))

    Aux.__view_children_items__ = []

    for opt in options:
        def aux(opt: str):
            @discord.ui.button(label = opt)
            async def callback(self, button: discord.ui.Button, interaction: discord.Interaction):
                self.selectedItems.append(opt)
                button.disabled = True

                if len(self.selectedItems) < len(options) - 1:
                    await interaction.message.edit(content = self.showSelected() + "\n" + f"Choisis ta **{len(self.selectedItems)+1}e option préférée** (le vote n'est valide que si toutes les options ont été classées)", view=self)
                else:
                    vote = self.selectedItems
                    #on a sélectionné toutes les options sauf une, il faut retrouver laquelle
                    vote.extend([x for x in options if x not in vote])

                    for child in self.children: #on désactive tous les boutons
                        child.disabled = True

                    votes[str(interaction.user.id)] = vote
                    saveData()

                    await interaction.message.edit(content = "**Ton vote a été enregistré**\nTu peux changer ton vote en réagissant de nouveau sur le serveur.\n\n" + self.showSelected(), view = self)
            
            return callback
        
        fonc = aux(opt)
        
        #add the button to Aux
        setattr(Aux, f"callback_{opt}", fonc)
        Aux.__view_children_items__.append(fonc)
    
    return Aux()

def condorcet(classements: Dict[int, List[str]], options: List[str]) -> Tuple[str, Dict[Tuple[str, str], Tuple[int, int]]]:
    """
    Compute the results of each duel from ranked voting ballots.
    Returns the Condorcet winner (or None if there is no winner) and detailed duel results.

    Args:
    - classements, dictionary {voter_id: [submissions_ranked_by_voter]}
    - submissions, list

    Returns:
    - the Condorcet winner (if it exists, the Borda_elim winner otherwise), str
    - detailed duel results, Dict[Tuple[str, str], Tuple[str, Tuple[int, int]]]
    """

    def borda_elim():
        optionsLoc = set(options)
        firstCount = None
        while len(optionsLoc) > 1:
            nbPoints = {c: 0 for c in optionsLoc}

            for ranking in classements.values():
                for i, sub in enumerate(filter(lambda x: x in nbPoints, ranking)):
                    nbPoints[sub] += len(optionsLoc) - i
            
            if firstCount is None:
                firstCount = nbPoints.copy()

            loser = min(nbPoints.items(), key=lambda x: (x[1], x[0]))[0]
            #we remove the submission that got the lowest amount of points
            #in case of a tie, the submission that got submitted later gets the priority for getting removed
            
            optionsLoc.remove(loser)
        
        if min(nbPoints.values()) == max(nbPoints.values()):
            return max(firstCount, key=lambda x: firstCount[x])

        return optionsLoc.pop()

    if classements == dict():
        #on prend la première option
        return options[0], dict()
    else:
        #{candidate_1: {candidate2: number_votes_candidate1_preferred_over_candidate2}}
        countsDuels: Dict[str, Dict[str, float]] = {c: {c2: 0 for c2 in options if c != c2} for c in options}

        for vote in classements.values():
            for i, subI in enumerate(vote):

                for j in range(i+1, len(vote)):
                    countsDuels[subI][vote[j]] += 1
        
        #{(winner, loser): (score_winner, score_loser)}
        winsDuels: Dict[Tuple[str, str], Tuple[float, float]] = dict()
        for i, subI in enumerate(options):
            for j in range(i+1, len(options)):
                subJ = options[j]

                duelIJ = countsDuels[subI][subJ]
                duelJI = countsDuels[subJ][subI]

                if duelIJ > duelJI:
                    winsDuels[subI, subJ] = (duelIJ, duelJI)
                elif duelIJ < duelJI:
                    winsDuels[subJ, subI] = (duelJI, duelIJ)
                else: #there is a tie, we use the timestamp as a tiebreaker
                    timestampI = subI[2]
                    timestampJ = subJ[2]

                    if timestampI <= timestampJ:
                        #the probability of having an equality on the timestamp is neglictible
                        #the submission submitted earlier gets the priority
                        winsDuels[subI, subJ] = (duelIJ, duelJI)
        
        #let's find the condorcet winner
        nbWins = {c: 0 for c in options}
        for (a, b) in winsDuels:
            nbWins[a] += 1
        
        biggestWinner, nbWinsBigger = max(nbWins.items(), key=lambda x: x[1])
        if nbWinsBigger == len(options) - 1: #the candidate won all its duels, it is an actual Condorcet winner
            return biggestWinner, winsDuels
        else:
            return borda_elim(), winsDuels