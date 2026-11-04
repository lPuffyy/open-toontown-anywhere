from direct.directnotify import DirectNotifyGlobal
from toontown.ai import HolidayBaseAI


class BingoNightHolidayAI(HolidayBaseAI.HolidayBaseAI):
    """Bingo Night as a holiday (Wednesdays in the original game): while it is on, every pond plays fish bingo. The game itself is
    FishBingoScheduleAI and DistributedPondBingoManagerAI; this only switches it on and off. Off unless gameconfig.json has
    "fish_bingo": "auto" (Wednesdays) or "on"."""
    notify = DirectNotifyGlobal.directNotify.newCategory('BingoNightHolidayAI')

    def start(self):
        schedule = getattr(self.air, 'fishBingoSchedule', None)
        if schedule is not None:
            schedule.holidayOn = True

    def stop(self):
        schedule = getattr(self.air, 'fishBingoSchedule', None)
        if schedule is not None:
            schedule.holidayOn = False
