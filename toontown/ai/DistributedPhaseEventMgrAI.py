import datetime
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class StartAndEndTime:
    """When a phased holiday starts and ends (two datetimes)."""

    def __init__(self, startTime, endTime):
        self.start = startTime
        self.end = endTime

    def isInBetween(self, phaseTime):
        return self.start < phaseTime < self.end

    def __repr__(self):
        return '(%s %s)' % (self.start, self.end)


class DistributedPhaseEventMgrAI(DistributedObjectAI):
    """Tells the clients which phase a phased holiday (the Silly Meter, Hydrant Zero, the street props helping in battle...) is in,
    and moves on to the next phase when its date comes (ported from the original game)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPhaseEventMgrAI')

    def __init__(self, air, startAndEndTimes, phaseDates):
        DistributedObjectAI.__init__(self, air)
        self.startAndEndTimes = startAndEndTimes
        self.phaseDates = phaseDates
        self.curPhase = -1
        self.calcCurPhase()
        self.isRunning = True          # the holiday manager only makes us while the holiday is on

    def getDates(self):
        """The holiday's start, each phase's start, and its end, for the client's Silly Meter clock."""
        holidayDates = [self.startAndEndTimes[-1].start] + list(self.phaseDates) + [self.startAndEndTimes[-1].end]
        return [(d.year, d.month, d.day, d.hour, d.minute, d.second) for d in holidayDates]

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.switchPhaseTaskName = self.uniqueName('switchPhase')
        self.setupNextPhase()

    def delete(self):
        self.stopSwitchPhaseTask()
        DistributedObjectAI.delete(self)

    def calcCurPhase(self):
        now = datetime.datetime.today()
        result = self.getNumPhases() - 1
        for index, phaseDate in enumerate(self.phaseDates):
            if now < phaseDate:
                result = index
                break
        self.curPhase = result

    def setupNextPhase(self):
        now = datetime.datetime.today()
        endTime = self.getPhaseEndTime(self.curPhase)
        if now < endTime:
            self.startSwitchPhaseTask((endTime - now).total_seconds())

    def startSwitchPhaseTask(self, waitTime):
        self.stopSwitchPhaseTask()
        # very long waits (the street props help "forever") are checked again daily, so the timer never overflows
        taskMgr.doMethodLater(min(waitTime, 86400.0), self.doSwitchPhase, self.switchPhaseTaskName)

    def stopSwitchPhaseTask(self):
        if hasattr(self, 'switchPhaseTaskName'):
            taskMgr.remove(self.switchPhaseTaskName)

    def doSwitchPhase(self, task):
        if 0 <= self.curPhase < self.getNumPhases() - 1 and datetime.datetime.today() >= self.getPhaseEndTime(self.curPhase):
            self.b_setCurPhase(self.curPhase + 1)
        self.setupNextPhase()
        return task.done

    def getPhaseEndTime(self, phase):
        if 0 <= phase < self.getNumPhases() - 1:
            return self.phaseDates[phase]
        if phase == self.getNumPhases() - 1:
            return self.startAndEndTimes[-1].end
        return datetime.datetime.today()

    def getNumPhases(self):
        return len(self.phaseDates) + 1

    def getCurPhase(self):
        return self.curPhase

    def getIsRunning(self):
        return self.isRunning

    def setCurPhase(self, newPhase):
        self.curPhase = newPhase

    def d_setCurPhase(self, newPhase):
        self.sendUpdate('setCurPhase', [newPhase])

    def b_setCurPhase(self, newPhase):
        self.setCurPhase(newPhase)
        self.d_setCurPhase(newPhase)

    def forcePhase(self, newPhase):
        """A magic word moves the holiday to a phase (until the next phase date)."""
        if not 0 <= newPhase < self.getNumPhases():
            return False
        self.b_setCurPhase(newPhase)
        return True

    def end(self):
        pass
