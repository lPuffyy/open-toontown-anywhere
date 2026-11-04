from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedBlackCatMgrAI(DistributedObjectAI):
    """Black Cat Day (from the original game): made for a new toon in the tutorial. A cat who says "Toontastic!" there becomes
    a black cat."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBlackCatMgrAI')

    def __init__(self, air, avId):
        DistributedObjectAI.__init__(self, air)
        self.avId = avId

    def getAvId(self):
        return self.avId

    def doBlackCatTransformation(self):
        if self.air.getAvatarIdFromSender() != self.avId:
            self.air.writeServerEvent('suspicious', self.air.getAvatarIdFromSender(), 'black cat request for %s' % self.avId)
            return
        av = self.air.doId2do.get(self.avId)
        if av is not None:
            self.air.writeServerEvent('blackCatMade', self.avId, 'turned into a black cat')
            av.makeBlackCat()
