from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.fishing import FishingTargetGlobals
from toontown.fishing.DistributedFishingTargetAI import DistributedFishingTargetAI

class DistributedFishingPondAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingPondAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.area = None
        self.targets = {}
        self.spots = []
        self.bingoMgr = None

    def setArea(self, area):
        self.area = area

    def getArea(self):
        return self.area

    def addSpot(self, spot):
        self.spots.append(spot)

    def createTargets(self):
        for _ in range(FishingTargetGlobals.getNumTargets(self.area)):
            target = DistributedFishingTargetAI(self.air)
            target.setPondDoId(self.doId)
            target.generateWithRequired(self.zoneId)
            self.targets[target.doId] = target
            target.startWandering()
        if simbase.config.GetBool('want-fish-bingo', 0):
            self.air.fishBingoSchedule.register(self)

    def startBingoNight(self):
        if self.bingoMgr or self.isDeleted():
            return
        from toontown.fishing.DistributedPondBingoManagerAI import DistributedPondBingoManagerAI
        self.bingoMgr = DistributedPondBingoManagerAI(self.air, self)
        self.bingoMgr.generateWithRequired(self.zoneId)
        mgr = self.bingoMgr
        # anglers already sitting at the pond join the game that is starting
        def seatThem(task):
            if self.bingoMgr is mgr and not mgr.isDeleted():
                for spot in self.spots:
                    if getattr(spot, 'avId', 0):
                        mgr.avatarEnter(spot.avId)
            return task.done
        taskMgr.doMethodLater(1.5, seatThem, 'bingoSeat-%d' % self.doId)

    def endBingoNight(self):
        mgr = self.bingoMgr
        if not mgr:
            return
        self.bingoMgr = None
        mgr.closeForTheNight()

    def delete(self):
        if simbase.config.GetBool('want-fish-bingo', 0):
            self.air.fishBingoSchedule.unregister(self)
        if self.bingoMgr:
            self.bingoMgr.requestDelete()
            self.bingoMgr = None
        for target in list(self.targets.values()):
            target.requestDelete()
        self.targets = {}
        DistributedObjectAI.delete(self)

    def hitTarget(self, targetId):
        avId = self.air.getAvatarIdFromSender()
        if targetId not in self.targets:
            self.notify.warning('hitTarget: unknown target %s from %s' % (targetId, avId))
            return
        for spot in self.spots:
            if spot.avId == avId:
                spot.handleHit()
                return
        self.notify.warning('hitTarget: avatar %s is not at a spot' % avId)
