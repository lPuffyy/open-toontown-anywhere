import datetime
import traceback

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import GameConfig
from toontown.toonbase import ToontownGlobals


class HolidayManagerAI:
    """Decides which holidays are on and tells the players. The district announces the list through its news manager; the client does the rest
    (street decorations, a spooky sky, the holiday's Speed Chat phrases). A holiday is on between two dates (the server's date), or the person
    running the server can force it on or off in gameconfig.json:  {"halloween": "auto"}  ("auto" = by date, "on", or "off"); the same for every
name in SCHEDULE. Holidays with a server side (Trick-or-Treat, caroling, fireworks, invasions, Bingo Night...) also get their runner
(see runnerFor) started and stopped with them."""
    notify = DirectNotifyGlobal.directNotify.newCategory('HolidayManagerAI')
    CHECK_EVERY = 60.0                # seconds between looks at the date and the settings

    # name -> (the holiday ids it turns on, first day, last day, weekdays or None); a day is (month, day), both ends included (a range may
    # wrap past New Year); weekdays is a set of datetime weekday numbers (Monday is 0) the holiday is on, or None for every day
    SCHEDULE = {
        'halloween': ([ToontownGlobals.HALLOWEEN_PROPS, ToontownGlobals.HALLOWEEN_COSTUMES], (10, 20), (11, 1), None),
        'trick_or_treat': ([ToontownGlobals.TRICK_OR_TREAT], (10, 20), (11, 1), None),
        'black_cat_day': ([ToontownGlobals.BLACK_CAT_DAY], (10, 31), (10, 31), None),
        'halloween_invasion': ([ToontownGlobals.HALLOWEEN], (10, 31), (11, 1), None),
        'winter': ([ToontownGlobals.WINTER_DECORATIONS, ToontownGlobals.WINTER_CAROLING], (12, 1), (1, 3), None),
        'new_years_fireworks': ([ToontownGlobals.NEWYEARS_FIREWORKS], (12, 31), (1, 1), None),
        'july4_fireworks': ([ToontownGlobals.JULY4_FIREWORKS], (6, 30), (7, 4), None),
        'valentines': ([ToontownGlobals.VALENTINES_DAY], (2, 7), (2, 15), None),
        'fish_bingo': ([ToontownGlobals.FISH_BINGO_NIGHT], (1, 1), (12, 31), {2}),
        'polar_place': ([ToontownGlobals.POLAR_PLACE_EVENT], (1, 1), (12, 31), None),
        'resistance_event': ([ToontownGlobals.RESISTANCE_EVENT], (1, 1), (12, 31), None),
        'jellybean_days': ([ToontownGlobals.JELLYBEAN_TROLLEY_HOLIDAY, ToontownGlobals.JELLYBEAN_FISHING_HOLIDAY, ToontownGlobals.JELLYBEAN_PARTIES_HOLIDAY], (1, 1), (12, 31), {5, 6}),
    }
    # holidays that change the economy, or were one-off promotions, are off unless gameconfig.json asks for them ("auto" or "on")
    DEFAULT_OFF = ('jellybean_days', 'polar_place', 'resistance_event', 'fish_bingo')

    @staticmethod
    def runnerFor(holidayId):
        """The server object that runs a holiday while it is on (ported from the original game), or None."""
        from toontown.ai import HolidayEventsAI as E
        runners = {ToontownGlobals.VALENTINES_DAY: E.ValentinesDayMgrAI,
                   ToontownGlobals.NEWYEARS_FIREWORKS: E.FireworkManagerAI,
                   ToontownGlobals.JULY4_FIREWORKS: E.FireworkManagerAI,
                   ToontownGlobals.HALLOWEEN: E.HolidaySuitInvasionManagerAI,
                   ToontownGlobals.POLAR_PLACE_EVENT: E.PolarPlaceEventMgrAI,
                   ToontownGlobals.RESISTANCE_EVENT: E.ResistanceEventMgrAI}
        if holidayId in runners:
            return runners[holidayId]
        if holidayId == ToontownGlobals.TRICK_OR_TREAT:
            from toontown.ai.TrickOrTreatMgrAI import TrickOrTreatMgrAI
            return TrickOrTreatMgrAI
        if holidayId == ToontownGlobals.WINTER_CAROLING:
            from toontown.ai.WinterCarolingMgrAI import WinterCarolingMgrAI
            return WinterCarolingMgrAI
        if holidayId == ToontownGlobals.BLACK_CAT_DAY:
            from toontown.ai.BlackCatHolidayMgrAI import BlackCatHolidayMgrAI
            return BlackCatHolidayMgrAI
        if holidayId == ToontownGlobals.FISH_BINGO_NIGHT:
            from toontown.fishing.BingoNightHolidayAI import BingoNightHolidayAI
            return BingoNightHolidayAI
        return None

    def __init__(self, air):
        self.air = air
        self.currentHolidays = {}      # holiday id -> the object that runs it (or None); the id being a key is what the game code checks
        self.forced = {}               # holiday id -> True/False, set by staff with a magic word until the server restarts

    def forceHoliday(self, holidayId, on):
        """A magic word turns a holiday on or off in this district (None goes back to the schedule)."""
        if on is None:
            self.forced.pop(holidayId, None)
        else:
            self.forced[holidayId] = bool(on)
        self.update()

    def isHolidayRunning(self, holidayId):
        return holidayId in self.currentHolidays

    def isMoreXpHolidayRunning(self):
        return ToontownGlobals.MORE_XP_HOLIDAY in self.currentHolidays

    @classmethod
    def scheduledIds(cls, today, setting=lambda name: 'auto'):
        """The holiday ids that are on for this date (a datetime.date). setting(name) gives 'auto', 'on', 'off' (or None for the holiday's default)."""
        ids = []
        for name, (holidayIds, first, last, weekdays) in sorted(cls.SCHEDULE.items()):
            mode = str(setting(name) or 'auto').lower()
            if mode == 'auto' and name in cls.DEFAULT_OFF and setting(name) is None:
                mode = 'off'
            day = (today.month, today.day)
            inRange = first <= day <= last if first <= last else (day >= first or day <= last)
            if mode == 'on' or (mode != 'off' and inRange and (weekdays is None or today.weekday() in weekdays)):
                ids.extend(holidayIds)
        return sorted(set(ids))

    # ---- running it
    def start(self):
        """Call once the district's news manager exists."""
        self.update()
        taskMgr.doMethodLater(self.CHECK_EVERY, self.__tick, 'holidayCheck')

    def stop(self):
        taskMgr.remove('holidayCheck')

    def __tick(self, task):
        try:
            self.update()
        except Exception:
            self.notify.warning('could not update the holidays: ' + traceback.format_exc())
        return task.again

    def update(self, today=None):
        today = today or datetime.date.today()
        wanted = set(self.scheduledIds(today, lambda name: GameConfig.get(name, None)))
        wanted |= {h for h, on in self.forced.items() if on}
        wanted -= {h for h, on in self.forced.items() if not on}
        if wanted == set(self.currentHolidays):
            return
        for holidayId in sorted(set(self.currentHolidays) - wanted):
            runner = self.currentHolidays.pop(holidayId, None)
            if runner is not None:
                try:
                    runner.stop()
                except Exception:
                    self.notify.warning('could not stop holiday %d: %s' % (holidayId, traceback.format_exc()))
            self.notify.info('holiday %d ended' % holidayId)
        for holidayId in sorted(wanted - set(self.currentHolidays)):
            runner = None
            try:
                cls = self.runnerFor(holidayId)
                if cls is not None:
                    runner = cls(self.air, holidayId)
                    runner.start()
            except Exception:
                runner = None
                self.notify.warning('could not start holiday %d: %s' % (holidayId, traceback.format_exc()))
            self.currentHolidays[holidayId] = runner
            self.notify.info('holiday %d started' % holidayId)
        news = getattr(self.air, 'newsManager', None)
        if news is not None:
            news.d_setHolidayIdList(sorted(self.currentHolidays))
