"""The Silly Meter story (ported from the original game, where it ran from May to July 2010) and the street props that help in battle.

The story is a set of holidays that follow each other on fixed dates: first Hydrant, Mailbox and Trashcan Zero wake up and learn new
moves, the Silly Meter goes up in Toon Hall stage by stage, battle numbers get silly words (the silly surge), the meter plummets when
the cogs invade, and from then on the hydrants, mailboxes and trash cans on the streets help toons fight (Squirt, Throw and Toon-Up).

The story only runs when gameconfig.json says when it starts: {"silly_meter_start": "2026-12-01 18:00"} (server time; the dates of
the original are shifted so the first day falls there). The street props helping in battle is the original game's normal state
after the story ended, so it is on outside the story as well, unless gameconfig.json has {"silly_props": "off"}."""
import datetime
from direct.directnotify import DirectNotifyGlobal
from toontown.ai import HolidayBaseAI
from toontown.ai.DistributedPhaseEventMgrAI import DistributedPhaseEventMgrAI, StartAndEndTime
from toontown.toonbase import ToontownGlobals as TG

D = datetime.datetime
FOREVER = D(2100, 1, 1)
STORY_START = D(2010, 5, 5, 8, 0)       # the first day of the original story; silly_meter_start takes its place

# holiday id -> (start, end, the dates its phases change), as in the original game
STORY = {
    TG.HYDRANT_ZERO_HOLIDAY: (D(2010, 5, 5, 8, 0), D(2010, 6, 12, 11, 55),
                              [D(2010, 5, 9, 11, 5), D(2010, 5, 13, 11, 5), D(2010, 5, 18, 11, 5), D(2010, 5, 21, 16, 5),
                               D(2010, 5, 22, 15, 30), D(2010, 6, 3, 15, 30)]),
    TG.TRASHCAN_ZERO_HOLIDAY: (D(2010, 5, 8, 12, 15), D(2010, 6, 12, 11, 55),
                               [D(2010, 5, 11, 11, 5), D(2010, 5, 15, 11, 5), D(2010, 5, 20, 11, 5), D(2010, 5, 23, 11, 5),
                                D(2010, 5, 29, 14, 10), D(2010, 6, 6, 14, 1)]),
    TG.MAILBOX_ZERO_HOLIDAY: (D(2010, 5, 9, 12, 0), D(2010, 6, 12, 11, 55),
                              [D(2010, 5, 16, 16, 55), D(2010, 5, 21, 16, 55), D(2010, 5, 23, 17, 5), D(2010, 6, 1, 11, 5),
                               D(2010, 6, 5, 12, 1), D(2010, 6, 8, 11, 45)]),
    TG.SILLYMETER_HOLIDAY: (D(2010, 5, 14, 0, 1), D(2010, 7, 14, 0, 1),
                            [D(2010, 5, 17, 16, 1), D(2010, 5, 19, 0, 1), D(2010, 5, 22, 14, 1), D(2010, 5, 24, 17, 1),
                             D(2010, 5, 26, 0, 1), D(2010, 5, 30, 10, 1), D(2010, 6, 2, 0, 1), D(2010, 6, 5, 12, 0),
                             D(2010, 6, 8, 10, 1), D(2010, 6, 9, 0, 1), D(2010, 6, 12, 10, 1), D(2010, 6, 12, 12, 1),
                             D(2010, 6, 13, 13, 30), D(2010, 6, 14, 0, 1), D(2010, 6, 28, 0, 1)]),
    TG.SILLY_SURGE_HOLIDAY: (D(2010, 5, 14, 0, 1), D(2010, 6, 13, 13, 30), []),
    TG.SILLY_CHATTER_ONE: (D(2010, 5, 14, 0, 0, 1), D(2010, 5, 25, 23, 59, 59), []),
    TG.SILLY_CHATTER_TWO: (D(2010, 5, 26, 0, 0, 1), D(2010, 6, 1, 23, 59, 59), []),
    TG.SILLY_CHATTER_THREE: (D(2010, 6, 2, 0, 0, 1), D(2010, 6, 17, 23, 59, 59), []),
    TG.SILLY_CHATTER_FOUR: (D(2010, 6, 18, 0, 0, 1), D(2010, 6, 27, 23, 59, 59), []),
    TG.SILLY_CHATTER_FIVE: (D(2010, 6, 28, 0, 0, 1), D(2010, 7, 13, 23, 59, 59), []),
    # the props start dancing at battles, then help (phase 1) a few days later, and never stop
    TG.HYDRANTS_BUFF_BATTLES: (D(2010, 6, 12, 12, 1), FOREVER, [D(2010, 6, 14, 3, 0)]),
    TG.MAILBOXES_BUFF_BATTLES: (D(2010, 6, 12, 12, 1), FOREVER, [D(2010, 6, 18, 0, 1)]),
    TG.TRASHCANS_BUFF_BATTLES: (D(2010, 6, 12, 12, 1), FOREVER, [D(2010, 6, 18, 0, 1)]),
}
PROP_BUFFS = (TG.HYDRANTS_BUFF_BATTLES, TG.MAILBOXES_BUFF_BATTLES, TG.TRASHCANS_BUFF_BATTLES)
STORY_END = max(end for start, end, phases in STORY.values() if end != FOREVER)


def parseStart(value):
    """silly_meter_start from gameconfig.json as a datetime, or None (not set or not a date)."""
    if not value or not isinstance(value, str):
        return None
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(value.strip(), fmt)
        except ValueError:
            pass
    return None


def storyTimes(holidayId, storyStart):
    """(start, end, phase dates) of a story holiday when the story starts at storyStart."""
    start, end, phases = STORY[holidayId]
    shift = storyStart - STORY_START
    return start + shift, (end if end == FOREVER else end + shift), [p + shift for p in phases]


def storyIds(now, storyStart):
    """The story holidays that are on at `now` (prop buffs are left to propsTimes)."""
    if storyStart is None:
        return []
    ids = []
    for holidayId in STORY:
        if holidayId in PROP_BUFFS:
            continue
        start, end, phases = storyTimes(holidayId, storyStart)
        if start <= now < end:
            ids.append(holidayId)
    return ids


def propsTimes(holidayId, now, storyStart, propsSetting):
    """(start, end, phase dates) for a street-prop holiday that is on at `now`, or None when it is off."""
    if storyStart is not None and storyStart <= now < STORY_END + (storyStart - STORY_START):
        times = storyTimes(holidayId, storyStart)
        if now < times[0]:
            return None                                   # the story is on and the props have not woken up yet
        return times                                      # the story's own dates (dancing first, helping a few days later)
    if str(propsSetting or 'auto').lower() == 'off':
        return None
    return now - datetime.timedelta(days=1), FOREVER, [now - datetime.timedelta(hours=1)]   # helping, the way the story left them


class PhaseEventHolidayAI(HolidayBaseAI.HolidayBaseAI):
    """Runs a phased holiday by putting its phase manager in the district's UberZone (every player in the district sees it)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('PhaseEventHolidayAI')
    MGR_CLASS = DistributedPhaseEventMgrAI

    def __init__(self, air, holidayId):
        HolidayBaseAI.HolidayBaseAI.__init__(self, air, holidayId)
        self.mgr = None
        self.runningState = 0

    def start(self):
        start, end, phases = self.air.holidayManager.phaseTimes(self.holidayId)
        self.mgr = self.MGR_CLASS(self.air, [StartAndEndTime(start, end)], phases)
        self.mgr.generateWithRequired(TG.UberZone)
        self.runningState = 1

    def stop(self):
        self.runningState = 0
        if self.mgr is not None:
            self.mgr.end()
            self.mgr.requestDelete()
            self.mgr = None

    def getRunningState(self):
        return self.runningState

    def getCurPhase(self):
        return self.mgr.getCurPhase() if self.mgr is not None else -1

    def getNumPhases(self):
        return self.mgr.getNumPhases() if self.mgr is not None else 0

    def forcePhase(self, newPhase):
        return self.mgr is not None and self.mgr.forcePhase(newPhase)


def runnerClass(holidayId):
    from toontown.ai.DistributedSillyMeterMgrAI import DistributedSillyMeterMgrAI
    from toontown.ai.DistributedHydrantZeroMgrAI import DistributedHydrantZeroMgrAI
    from toontown.ai.DistributedMailboxZeroMgrAI import DistributedMailboxZeroMgrAI
    from toontown.ai.DistributedTrashcanZeroMgrAI import DistributedTrashcanZeroMgrAI
    mgrs = {TG.SILLYMETER_HOLIDAY: DistributedSillyMeterMgrAI,
            TG.HYDRANT_ZERO_HOLIDAY: DistributedHydrantZeroMgrAI,
            TG.MAILBOX_ZERO_HOLIDAY: DistributedMailboxZeroMgrAI,
            TG.TRASHCAN_ZERO_HOLIDAY: DistributedTrashcanZeroMgrAI}
    if holidayId in mgrs:
        return type('%sHolidayAI' % mgrs[holidayId].__name__, (PhaseEventHolidayAI,), {'MGR_CLASS': mgrs[holidayId]})
    if holidayId in PROP_BUFFS:
        return PhaseEventHolidayAI
    return None
