import json
import os
import re

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedTrophyMgrAI(DistributedObjectAI):
    """Building trophies: a toon scores one point for each floor of a toon building it rescued, for as long as the Cogs do not take
    that building back. The score shows as a star by the toon's name, and the ten best toons are listed on the board in every
    Toon HQ.

    The buildings (and who saved them) are saved per district and replayed through addTrophy when a district starts, so the scores
    rebuild themselves. Each district writes its own share to a small file in the data folder; the board and the stars add up all
    districts, so a toon's star and place do not depend on where it is playing."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrophyMgrAI')
    NUM_LEADERS = 10
    FLUSH_DELAY = 10.0          # seconds between a change and the Toon HQ boards being sent the new list
    RELOAD_EVERY = 60.0         # seconds between looks at the other districts' files

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.scores = {}            # this district: avId -> [name, floors]
        self.others = {}            # the other districts: avId -> [name, floors], summed
        self.leaderInfo = ([], [], [])
        self.otherStamp = None

    # ---- files
    def __folder(self):
        return getattr(self.air, 'dataFolder', '') or ''

    def __ownFile(self):
        name = re.sub(r'[^A-Za-z0-9]+', '_', str(getattr(self.air, 'districtName', '') or self.air.ourChannel))
        return os.path.join(self.__folder(), 'trophies_%s.json' % name)

    def __save(self):
        path = self.__ownFile()
        try:
            tmp = path + '.tmp'
            with open(tmp, 'w') as f:
                json.dump({str(k): v for k, v in self.scores.items()}, f)
            os.replace(tmp, path)
        except Exception as e:
            self.notify.warning('could not save the trophy scores: %s' % e)

    def __loadOthers(self):
        """Read the other districts' files. Returns True when they changed."""
        own = os.path.abspath(self.__ownFile())
        folder = self.__folder() or '.'
        merged, stamp = {}, []
        try:
            names = sorted(n for n in os.listdir(folder) if n.startswith('trophies_') and n.endswith('.json'))
        except Exception:
            names = []
        for n in names:
            path = os.path.join(folder, n)
            if os.path.abspath(path) == own:
                continue
            try:
                stamp.append((n, os.path.getmtime(path)))
                with open(path) as f:
                    for avId, (name, floors) in json.load(f).items():
                        entry = merged.setdefault(int(avId), [name, 0])
                        entry[1] += int(floors)
            except Exception as e:
                self.notify.warning('could not read %s: %s' % (n, e))
        if stamp == self.otherStamp:
            return False
        self.otherStamp = stamp
        self.others = merged
        return True

    # ---- the scores
    def getScore(self, avId):
        return self.scores.get(avId, [None, 0])[1] + self.others.get(avId, [None, 0])[1]

    def __rebuildLeaders(self):
        totals = {}
        for table in (self.others, self.scores):
            for avId, (name, floors) in table.items():
                entry = totals.setdefault(avId, [name, 0])
                entry[0] = name or entry[0]
                entry[1] += floors
        best = sorted(((floors, avId, name) for avId, (name, floors) in totals.items() if floors > 0), key=lambda e: (-e[0], e[1]))[:self.NUM_LEADERS]
        info = ([avId for floors, avId, name in best], [name for floors, avId, name in best], [floors for floors, avId, name in best])
        if info != self.leaderInfo:
            self.leaderInfo = info
            messenger.send('leaderboardChanged')
            taskMgr.remove(self.uniqueName('trophyFlush'))
            taskMgr.doMethodLater(self.FLUSH_DELAY, self.__flush, self.uniqueName('trophyFlush'))

    def __flush(self, task):
        messenger.send('leaderboardFlush')
        return task.done

    def __tellToon(self, avId):
        av = self.air.doId2do.get(avId)
        if av is not None and hasattr(av, 'd_setTrophyScore'):
            score = self.getScore(avId)
            av.trophyScore = score
            av.d_setTrophyScore(score)

    def __changed(self, avId):
        self.__save()
        self.__rebuildLeaders()
        self.__tellToon(avId)

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.__loadOthers()
        self.__rebuildLeaders()
        taskMgr.doMethodLater(self.RELOAD_EVERY, self.__reload, self.uniqueName('trophyReload'))

    def delete(self):
        taskMgr.remove(self.uniqueName('trophyReload'))
        taskMgr.remove(self.uniqueName('trophyFlush'))
        DistributedObjectAI.delete(self)

    def __reload(self, task):
        try:
            before = dict(self.others)
            if self.__loadOthers():
                self.__rebuildLeaders()
                for avId in set(before) | set(self.others):
                    if before.get(avId, [None, 0])[1] != self.others.get(avId, [None, 0])[1]:
                        self.__tellToon(avId)
        except Exception as e:
            self.notify.warning('trophy reload failed: %s' % e)
        return task.again

    # ---- called by the game
    def requestTrophyScore(self):
        """A client asks for its own toon's score (sent when it sees toons appear)."""
        avId = self.air.getAvatarIdFromSender()
        self.__tellToon(avId)

    def getLeaderInfo(self):
        return self.leaderInfo

    def addTrophy(self, avId, name, numFloors):
        entry = self.scores.setdefault(avId, [name, 0])
        entry[0] = name or entry[0]
        entry[1] += numFloors
        self.notify.info('trophy: %s (%s) +%d floors, now %d here' % (name, avId, numFloors, entry[1]))
        self.__changed(avId)

    def removeTrophy(self, avId, numFloors):
        entry = self.scores.get(avId)
        if entry is None:
            return
        entry[1] -= numFloors
        if entry[1] <= 0:
            del self.scores[avId]
        self.notify.info('trophy: %s -%d floors' % (avId, numFloors))
        self.__changed(avId)
