"""The server side of the holidays (ported from the original game's holiday managers). The holiday manager starts one of these when
its holiday begins and stops it when the holiday ends. Holidays that only change what the clients show have none."""
import random
from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from toontown.ai import HolidayBaseAI
from toontown.suit import SuitDNA
from toontown.toonbase import ToontownGlobals


class BulletinBoardHolidayAI(HolidayBaseAI.HolidayBaseAI):
    """A holiday other code checks for on the bulletin board (bboard)."""
    PostName = None

    def start(self):
        bboard.post(self.PostName, True)

    def stop(self):
        bboard.remove(self.PostName)


class ValentinesDayMgrAI(BulletinBoardHolidayAI):
    PostName = 'ValentinesDay'


class EventObjectHolidayAI(HolidayBaseAI.HolidayBaseAI):
    """A holiday that puts one object in one zone (a shop interior) for players to talk to."""
    PostName = None
    EVENT_ZONE = None

    def objectClass(self):
        raise NotImplementedError

    def start(self):
        self.obj = self.objectClass()(self.air)
        self.obj.generateWithRequired(self.EVENT_ZONE)
        bboard.post(self.PostName)

    def stop(self):
        bboard.remove(self.PostName)
        if self.obj is not None and not self.obj.isDeleted():
            self.obj.requestDelete()
        self.obj = None


class PolarPlaceEventMgrAI(EventObjectHolidayAI):
    PostName = 'polarPlaceEvent'
    EVENT_ZONE = 3821          # Hibernation Vacations

    def objectClass(self):
        from toontown.ai.DistributedPolarPlaceEffectMgrAI import DistributedPolarPlaceEffectMgrAI
        return DistributedPolarPlaceEffectMgrAI


class ResistanceEventMgrAI(EventObjectHolidayAI):
    PostName = 'resistanceEvent'
    EVENT_ZONE = 9720          # Talking in Your Sleep Voiceover Training

    def objectClass(self):
        from toontown.ai.DistributedResistanceEmoteMgrAI import DistributedResistanceEmoteMgrAI
        return DistributedResistanceEmoteMgrAI


class FireworkManagerAI(HolidayBaseAI.HolidayBaseAI):
    """A fireworks holiday: a show in every playground at the top of each hour."""
    notify = DirectNotifyGlobal.directNotify.newCategory('FireworkManagerAI')
    zoneToStyleDict = {ToontownGlobals.DockHarbor: 5,
                       ToontownGlobals.ToontownCentral: 0,
                       ToontownGlobals.TheBrrrgh: 4,
                       ToontownGlobals.MelodyMeadow: 3,
                       ToontownGlobals.GardenGrove: 1,
                       ToontownGlobals.OutdoorZone: 0,
                       ToontownGlobals.SpeedwayPark: 0,
                       ToontownGlobals.SlumberSprings: 2}

    def __init__(self, air, holidayId):
        HolidayBaseAI.HolidayBaseAI.__init__(self, air, holidayId)
        self.fireworkShows = {}
        self.waitTaskName = 'waitStartFireworkShows-%d' % holidayId

    def start(self):
        self.__waitForNextShow()

    def stop(self):
        taskMgr.remove(self.waitTaskName)
        self.stopAllShows()

    def __waitForNextShow(self):
        import time
        now = time.localtime()
        taskMgr.doMethodLater((60 - now[4]) * 60 - now[5], self.__startAllShows, self.waitTaskName)

    def __startAllShows(self, task):
        for hood in self.air.hoods:
            style = self.zoneToStyleDict.get(hood.canonicalHoodId)
            if style is not None:
                self.startShow(hood.zoneId, style)
        self.__waitForNextShow()
        return Task.done

    def startShow(self, zoneId, style=0):
        if zoneId in self.fireworkShows:
            return 0
        from toontown.effects.DistributedFireworkShowAI import DistributedFireworkShowAI
        show = DistributedFireworkShowAI(self.air, self)
        show.generateWithRequired(zoneId)
        self.fireworkShows[zoneId] = show
        show.d_startShow(self.holidayId, style)
        return 1

    def stopShow(self, zoneId):
        show = self.fireworkShows.pop(zoneId, None)
        if show is None:
            return 0
        if not show.isDeleted():
            show.requestDelete()
        return 1

    def stopAllShows(self):
        for zoneId in list(self.fireworkShows):
            self.stopShow(zoneId)

    def isShowRunning(self, zoneId):
        return zoneId in self.fireworkShows


class HolidaySuitInvasionManagerAI(HolidayBaseAI.HolidayBaseAI):
    """A holiday invasion: while it lasts, whenever this district has no invasion one starts (Halloween: skelecogs)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('HolidaySuitInvasionManagerAI')
    CHECK_EVERY = 60.0
    NUM_SUITS = 1000

    def __init__(self, air, holidayId):
        HolidayBaseAI.HolidayBaseAI.__init__(self, air, holidayId)
        self.taskName = 'holidayInvasion-%d' % holidayId

    def start(self):
        self.__check(None)
        taskMgr.doMethodLater(self.CHECK_EVERY, self.__check, self.taskName)

    def stop(self):
        taskMgr.remove(self.taskName)

    def __check(self, task):
        mgr = getattr(self.air, 'suitInvasionManager', None)
        if mgr is not None and not mgr.getInvading():
            skeleton = self.holidayId in (ToontownGlobals.HALLOWEEN, ToontownGlobals.SKELECOG_INVASION)
            mgr.startInvasion(random.choice(SuitDNA.suitHeadTypes), self.NUM_SUITS, skeleton)
        if task is not None:
            return task.again
