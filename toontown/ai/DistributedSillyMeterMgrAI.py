from direct.directnotify import DirectNotifyGlobal
from toontown.ai.DistributedPhaseEventMgrAI import DistributedPhaseEventMgrAI


class DistributedSillyMeterMgrAI(DistributedPhaseEventMgrAI):
    """The Silly Meter in Toon Hall: which stage it is at (the scientists in Toon Hall listen for SillyMeterPhase)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedSillyMeterMgrAI')

    def __init__(self, air, startAndEndTimes, phaseDates):
        DistributedPhaseEventMgrAI.__init__(self, air, startAndEndTimes, phaseDates)
        air.SillyMeterMgr = self

    def setCurPhase(self, newPhase):
        DistributedPhaseEventMgrAI.setCurPhase(self, newPhase)
        messenger.send('SillyMeterPhase', [newPhase])

    def calcCurPhase(self):
        DistributedPhaseEventMgrAI.calcCurPhase(self)
        messenger.send('SillyMeterPhase', [self.curPhase])

    def end(self):
        messenger.send('SillyMeterPhase', [len(self.phaseDates) + 1])

    def delete(self):
        if getattr(self.air, 'SillyMeterMgr', None) is self:
            del self.air.SillyMeterMgr
        DistributedPhaseEventMgrAI.delete(self)
