import time
from direct.directnotify import DirectNotifyGlobal

class FishBingoScheduleAI:
    """Fish bingo is not always on: it runs for a stretch at the start of every hour, a Bingo Night in the manner of the original,
    and Toon HQ says when it starts and ends. Every pond in every district follows the same clock."""
    notify = DirectNotifyGlobal.directNotify.newCategory('FishBingoScheduleAI')
    PERIOD = 60 * 60            # seconds from one start to the next
    DURATION = 20 * 60          # seconds it runs for
    CHECK = 10.0
    ENABLED = False             # fish bingo is switched off for now: set True to bring the hourly Bingo Night back

    def __init__(self, air):
        self.air = air
        self.ponds = []
        self.active = False
        taskMgr.doMethodLater(self.CHECK, self.__tick, 'fishBingoSchedule')

    def register(self, pond):
        self.ponds.append(pond)
        if self.active:
            pond.startBingoNight()

    def unregister(self, pond):
        if pond in self.ponds:
            self.ponds.remove(pond)

    def shouldRun(self):
        if not self.ENABLED:
            return False
        return (time.time() % self.PERIOD) < self.DURATION

    def __tick(self, task):
        want = self.shouldRun()
        if want != self.active:
            self.active = want
            self.notify.info('bingo night %s' % ('begins' if want else 'ends'))
            for pond in list(self.ponds):
                if want:
                    pond.startBingoNight()
                else:
                    pond.endBingoNight()
            news = getattr(self.air, 'newsManager', None)
            if news:
                news.sendUpdate('setBingoStart' if want else 'setBingoEnd', [])
        return task.again
