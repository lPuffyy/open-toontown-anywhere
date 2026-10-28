import math
import random
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedNodeAI import DistributedNodeAI
from direct.distributed.ClockDelta import globalClockDelta
from toontown.fishing import FishingTargetGlobals

class DistributedFishingTargetAI(DistributedNodeAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingTargetAI')

    def __init__(self, air):
        DistributedNodeAI.__init__(self, air)
        self.pondDoId = 0
        self.state = (FishingTargetGlobals.OFF, 0.0, 0.0, 0.0, 0)

    def setPondDoId(self, pondDoId):
        self.pondDoId = pondDoId

    def getPondDoId(self):
        return self.pondDoId

    def getState(self):
        return self.state

    def startWandering(self):
        self.__step()

    def __step(self, task=None):
        pond = self.air.doId2do.get(self.pondDoId)
        if pond is None:
            return
        maxRadius = FishingTargetGlobals.getTargetRadius(pond.getArea())
        angle = random.uniform(0.0, 2 * math.pi)
        radius = random.uniform(0.0, maxRadius)
        t = FishingTargetGlobals.StepTime
        stamp = globalClockDelta.getRealNetworkTime(bits=16)
        self.state = (FishingTargetGlobals.MOVING, angle, radius, t, stamp)
        self.sendUpdate('setState', list(self.state))
        # swim there, then hang around for a few seconds before picking the next spot
        taskMgr.doMethodLater(t + random.uniform(3.0, 8.0), self.__step, self.uniqueName('wander'))

    def delete(self):
        taskMgr.remove(self.uniqueName('wander'))
        DistributedNodeAI.delete(self)
