from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedScavengerHuntTargetAI(DistributedObjectAI):
    """Sits in one zone of a scavenger hunt and waits for a toon there to say the hunt's phrase."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedScavengerHuntTargetAI')

    def __init__(self, air, goal, huntMgr):
        DistributedObjectAI.__init__(self, air)
        self.goal = goal
        self.huntMgr = huntMgr

    def attemptScavengerHunt(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or av.zoneId != self.zoneId:
            return
        self.huntMgr.avatarAttemptingGoal(avId, self.goal)
