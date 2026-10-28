from direct.directnotify import DirectNotifyGlobal
from toontown.fishing import FishGlobals

class FishManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('FishManagerAI')

    def __init__(self, air):
        self.air = air

    def creditFishTank(self, av):
        """Sell everything in the tank. Returns True when the toon earned a new collection trophy."""
        numFish = len(av.fishTank)
        value = av.fishTank.getTotalValue()
        av.fishTank.makeFromNetLists([], [], [])
        av.d_setFishTank(*av.fishTank.getNetLists())
        if value > 0:
            av.addMoney(value)
        if numFish > 0:
            av.toonUp(FishGlobals.HealAmount * numFish)

        trophies = list(av.getFishingTrophies())
        earned = min(len(av.fishCollection) // FishGlobals.FISH_PER_BONUS, len(FishGlobals.TrophyDict) - 1)
        if len(av.fishCollection) >= FishGlobals.getTotalNumFish():
            earned = len(FishGlobals.TrophyDict)
        newTrophy = False
        while len(trophies) < earned:
            trophies.append(len(trophies))
            newTrophy = True
        if newTrophy:
            av.b_setFishingTrophies(trophies)
            av.b_setMaxHp(av.getMaxHp() + 1)
            av.toonUp(av.getMaxHp())
        return newTrophy
