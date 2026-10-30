import random
from direct.directnotify import DirectNotifyGlobal
from toontown.suit import SuitDNA
from toontown.toonbase import GameConfig
from toontown.toonbase import ToontownGlobals

class SuitInvasionManagerAI:
    """One Cog invasion at a time in this district. Summoned by a Toon, or started now and then by itself, like the live game's."""
    notify = DirectNotifyGlobal.directNotify.newCategory('SuitInvasionManagerAI')
    RandomCogCount = 1000
    RandomDelay = (10 * 60, 25 * 60)       # seconds between one random invasion ending (or the server starting) and the next
    EXCLUDED = ()
    DurationMinutes = 30                     # an invasion also ends by itself after this long (gameconfig.json: invasion_minutes), so one nobody finishes does not run forever
    SAFE_DISTRICTS = ('Silly Meadow',)       # districts that never have an invasion

    def __init__(self, air):
        self.air = air
        self.cogType = None
        self.skeleton = 0
        self.numSuits = 0
        self.total = 0
        self.nextUpdate = 0

    def getInvadingCog(self):
        if self.cogType is None:
            return None, 0
        return self.cogType, self.skeleton

    def getInvading(self):
        return self.cogType is not None

    def isSafeDistrict(self):
        return getattr(self.air, 'districtName', '') in self.SAFE_DISTRICTS

    def scheduleRandom(self, first=True):
        if self.isSafeDistrict():
            return
        taskMgr.remove('suitInvasionRandom')
        delay = random.uniform(60, 4 * 60) if first else random.uniform(*self.RandomDelay)      # the first one comes soon after the district opens
        taskMgr.doMethodLater(delay, self.__randomInvasion, 'suitInvasionRandom')

    def __randomInvasion(self, task):
        if not self.getInvading():
            names = [n for n in SuitDNA.suitHeadTypes if n not in self.EXCLUDED]
            self.startInvasion(random.choice(names), self.RandomCogCount, random.random() < 0.1)
        self.scheduleRandom(False)
        return task.done

    def startInvasion(self, cogType, numSuits, skeleton=False):
        if self.isSafeDistrict() or self.getInvading() or cogType not in SuitDNA.suitHeadTypes:
            return False
        self.cogType = cogType
        self.skeleton = 1 if skeleton else 0
        self.numSuits = self.total = int(numSuits)
        self.nextUpdate = self.total - max(1, self.total // 10)
        self.notify.warning('invasion begins: %s x%d skeleton=%d' % (cogType, numSuits, self.skeleton))
        self.__broadcast(ToontownGlobals.SuitInvasionBegin)
        self.__publish()
        taskMgr.remove('suitInvasionTimeout')
        taskMgr.doMethodLater(max(0.1, float(GameConfig.get('invasion_minutes', self.DurationMinutes))) * 60, self.__timeout, 'suitInvasionTimeout')
        return True

    def __timeout(self, task):
        self.notify.warning('invasion of %s ends: time is up with %d left' % (self.cogType, self.numSuits))
        self.stopInvasion()
        return task.done

    def stopInvasion(self):
        if not self.getInvading():
            return
        taskMgr.remove('suitInvasionTimeout')
        self.__broadcast(ToontownGlobals.SuitInvasionEnd)
        self.cogType = None
        self.skeleton = 0
        self.numSuits = self.total = 0
        self.__publish()

    def handleSuitDefeated(self):
        if not self.getInvading():
            return
        self.numSuits -= 1
        if self.numSuits <= 0:
            self.stopInvasion()
            return
        if self.numSuits <= self.nextUpdate:
            self.nextUpdate = self.numSuits - max(1, self.total // 10)
            self.__broadcast(ToontownGlobals.SuitInvasionUpdate)
        self.__publish()

    def sendBulletin(self, avId):
        if self.getInvading() and getattr(self.air, 'newsManager', None):
            self.air.newsManager.sendUpdateToAvatarId(avId, 'setInvasionStatus', [ToontownGlobals.SuitInvasionBulletin, self.cogType, self.numSuits, self.skeleton])

    def __broadcast(self, msgType):
        if getattr(self.air, 'newsManager', None):
            self.air.newsManager.sendUpdate('setInvasionStatus', [msgType, self.cogType, max(0, self.numSuits), self.skeleton])

    def __publish(self):
        """Let the Districts page in every district see this one's invasion."""
        stats = getattr(self.air, 'districtStats', None)
        if stats is not None:
            stats.b_setInvasion(self.cogType or '', self.skeleton, max(0, self.numSuits))
