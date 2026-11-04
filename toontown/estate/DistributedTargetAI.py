"""The target that floats over an estate while its cannons are rented (from the original game).

Some random time after it resets, the target lights up worth 1 laff point with 15 seconds on the clock. Every hit doubles what it is
worth and cuts the time; when the time runs out everyone who was in the estate when the streak started (and is still there) is
healed by that much. It also keeps the estate's pinball high score."""
import random
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

MIN_WAIT_TIME = 5
MAX_WAIT_TIME = 30
FIRST_HIT_TIME = 15
MAX_SCORE = 134217728


class DistributedTargetAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTargetAI')

    def __init__(self, air, x, y, z):
        DistributedObjectAI.__init__(self, air)
        self.pos = [x, y, z]
        self.participants = []
        self.enabled = 0
        self.score = 0
        self.hitTime = FIRST_HIT_TIME
        self.pinballHiScore = 0
        self.pinballHiScorer = ''

    def delete(self):
        self.__stopTasks()
        DistributedObjectAI.delete(self)

    def __stopTasks(self):
        taskMgr.remove(self.taskName('start-score'))
        taskMgr.remove(self.taskName('scoreTimer'))

    def getPosition(self):
        return self.pos

    def start(self):
        self.reset()

    def reset(self):
        self.__stopTasks()
        self.enabled = 0
        self.score = 0
        self.sendUpdate('setState', [0, 0, 0])
        taskMgr.doMethodLater(random.random() * MAX_WAIT_TIME + MIN_WAIT_TIME, self.__startScore, self.taskName('start-score'))

    def __startScore(self, task):
        self.enabled = 1
        self.score = 1
        self.participants = self.__estateToons()       # toons that walk in later don't share this streak's reward
        self.hitTime = FIRST_HIT_TIME
        self.sendUpdate('setState', [1, self.score, self.hitTime])
        taskMgr.doMethodLater(self.hitTime, self.__timerExpired, self.taskName('scoreTimer'))
        return task.done

    def __estateToons(self):
        mgr = getattr(self.air, 'estateMgr', None)
        if mgr is None:
            return []
        ownerId = mgr.getOwnerFromZone(self.zoneId)
        if not ownerId:
            return []
        return list({ownerId} | set(mgr.visitors.get(ownerId, ())))

    def __targetHit(self):
        if not self.enabled:
            return
        taskMgr.remove(self.taskName('scoreTimer'))
        self.score = min(self.score * 2 if self.score > 0 else 2, MAX_SCORE)
        if self.hitTime >= 4:
            self.hitTime -= 2
        else:
            self.hitTime /= 2.0
        self.sendUpdate('setState', [1, self.score, self.hitTime])
        taskMgr.doMethodLater(self.hitTime, self.__timerExpired, self.taskName('scoreTimer'))

    def __timerExpired(self, task):
        if int(self.score) > 0:
            self.__doReward()
            self.sendUpdate('setReward', [int(self.score)])
        self.reset()
        return task.done

    def __doReward(self):
        here = set(self.__estateToons())
        for avId in self.participants:
            av = self.air.doId2do.get(avId)
            if av is not None and avId in here:
                av.toonUp(int(self.score))

    # client messages
    def setResult(self, avId):
        if avId and avId == self.air.getAvatarIdFromSender():
            self.__targetHit()

    def setBonus(self, bonus):
        if self.enabled:
            self.score = min(self.score + max(0.0, min(float(bonus), 1.0)), MAX_SCORE)   # (the client sends half a point)
            self.sendUpdate('setState', [1, self.score, self.hitTime])

    def setCurPinballScore(self, avId, curScore, multiplier):
        if avId != self.air.getAvatarIdFromSender():
            return
        total = curScore * multiplier
        if total > self.pinballHiScore:
            toon = self.air.doId2do.get(avId)
            self.b_setPinballHiScorer(toon.getName() if toon is not None else '')
            self.b_setPinballHiScore(total)

    # pinball high score
    def getPinballHiScorer(self):
        return self.pinballHiScorer

    def getPinballHiScore(self):
        return self.pinballHiScore

    def b_setPinballHiScorer(self, name):
        self.pinballHiScorer = name
        self.sendUpdate('setPinballHiScorer', [name])

    def b_setPinballHiScore(self, score):
        self.pinballHiScore = score
        self.sendUpdate('setPinballHiScore', [score])
