import random
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.fishing import FishGlobals
from toontown.fishing.FishBase import FishBase

class DistributedFishingSpotAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingSpotAI')

    def __init__(self, air, pond, posHpr):
        DistributedObjectAI.__init__(self, air)
        self.pond = pond
        self.posHpr = posHpr
        self.avId = 0
        self.casting = False

    def getPondDoId(self):
        return self.pond.doId

    def getPosHpr(self):
        return self.posHpr

    def requestEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        if self.avId != 0:
            self.sendUpdateToAvatarId(avId, 'rejectEnter', [])
            return
        self.avId = avId
        self.casting = False
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__avatarGone)
        self.d_setOccupied(avId)
        self.d_setMovie(FishGlobals.EnterMovie)
        if self.pond.bingoMgr:
            self.pond.bingoMgr.avatarEnter(avId)

    def requestExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.avId:
            return
        self.__leave(sendMovie=True)

    def __avatarGone(self):
        self.__leave(sendMovie=False)

    def __leave(self, sendMovie):
        if self.avId == 0:
            return
        self.ignore(self.air.getAvatarExitEvent(self.avId))
        if sendMovie:
            self.d_setMovie(FishGlobals.ExitMovie)
        if self.pond.bingoMgr:
            self.pond.bingoMgr.avatarExit(self.avId)
        self.avId = 0
        self.casting = False
        self.d_setOccupied(0)

    def d_setOccupied(self, avId):
        self.sendUpdate('setOccupied', [avId])

    def d_setMovie(self, mode, code=0, d1=0, d2=0, d3=0, power=0.0, h=0.0):
        self.sendUpdate('setMovie', [mode, code, d1, d2, d3, power, h])

    def doCast(self, power, heading):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.avId:
            return
        rod = av.getFishingRod()
        if av.isFishTankFull() or not av.takeMoney(FishGlobals.getCastCost(rod), False):
            self.casting = False
            return
        self.casting = True
        self.d_setMovie(FishGlobals.CastMovie, power=power, h=heading)

    def handleHit(self):
        if not self.casting:
            return
        self.casting = False
        av = self.air.doId2do.get(self.avId)
        if av is None:
            return
        rod = av.getFishingRod()
        itemId = self.air.questManager.findItemInWater(av, self.pond.getArea())
        if itemId is not None:
            self.d_setMovie(FishGlobals.PullInMovie, FishGlobals.QuestItem, itemId)
            return
        roll = random.randint(1, 100)
        item = FishGlobals.Nothing
        for cutoff in FishGlobals.SortedProbabilityCutoffs:
            if roll <= cutoff:
                item = FishGlobals.ProbabilityDict[cutoff]
                break
        if item == FishGlobals.FishItem:
            ok, genus, species, weight = FishGlobals.getRandomFishVitals(self.pond.getArea(), rod)
            if not ok:
                item = FishGlobals.BootItem
            else:
                fish = FishBase(genus, species, weight)
                if not av.addFishToTank(fish):
                    self.d_setMovie(FishGlobals.PullInMovie, FishGlobals.OverTankLimit)
                    return
                result = av.fishCollection.collectFish(fish)
                code = FishGlobals.FishItem
                if result == FishGlobals.COLLECT_NEW_ENTRY:
                    code = FishGlobals.FishItemNewEntry
                elif result == FishGlobals.COLLECT_NEW_RECORD:
                    code = FishGlobals.FishItemNewRecord
                if result != FishGlobals.COLLECT_NO_UPDATE:
                    av.d_setFishCollection(*av.fishCollection.getNetLists())
                self.d_setMovie(FishGlobals.PullInMovie, code, genus, species, weight)
                return
        if item == FishGlobals.JellybeanItem:
            amount = FishGlobals.Rod2JellybeanDict[rod]
            av.addMoney(amount)
            self.d_setMovie(FishGlobals.PullInMovie, FishGlobals.JellybeanItem, amount)
            return
        self.d_setMovie(FishGlobals.PullInMovie, FishGlobals.BootItem)

    def sellFish(self):
        pass
