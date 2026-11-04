"""A scavenger hunt holiday (from the original game): a listener sits in each goal's zone, and a toon who says the right Speed Chat
phrase there finds that goal. Finding one pays jelly beans; finding them all gives the holiday's reward.

The original kept each toon's finds in an UberDOG data store; here each toon's finds for this year's hunt are a small file in
holiday_data/<hunt>/<avId>.json (one file per toon, so the districts never write the same file)."""
import datetime
import json
import os
from direct.directnotify import DirectNotifyGlobal
from toontown.ai import HolidayBaseAI

SAVE_DIR = 'holiday_data'


class ScavengerHuntMgrAI(HolidayBaseAI.HolidayBaseAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('ScavengerHuntMgrAI')
    huntName = 'scavenger_hunt'
    GOALS = {}                   # goal id -> zone the listener sits in

    def __init__(self, air, holidayId):
        HolidayBaseAI.HolidayBaseAI.__init__(self, air, holidayId)
        self.targets = {}

    def targetClass(self):
        from toontown.ai.DistributedScavengerHuntTargetAI import DistributedScavengerHuntTargetAI
        return DistributedScavengerHuntTargetAI

    def huntKey(self):
        """This year's hunt. A hunt that runs past New Year (winter) belongs to the year it started in."""
        today = datetime.date.today()
        return '%s-%d' % (self.huntName, today.year - 1 if today.month < 6 and self.startsLateInYear() else today.year)

    def startsLateInYear(self):
        return False

    def start(self):
        cls = self.targetClass()
        for goal, zoneId in self.GOALS.items():
            target = cls(self.air, goal, self)
            target.generateWithRequired(zoneId)
            self.targets[goal] = target
        self.notify.info('%s started (%d targets)' % (self.huntName, len(self.targets)))

    def stop(self):
        for target in self.targets.values():
            if not target.isDeleted():
                target.requestDelete()
        self.targets = {}

    # progress -------------------------------------------------------------------------------------------------------
    def __path(self, avId):
        return os.path.join(SAVE_DIR, self.huntKey(), '%d.json' % avId)

    def foundGoals(self, avId):
        try:
            with open(self.__path(avId)) as f:
                return [int(g) for g in json.load(f)]
        except Exception:
            return []

    def __saveGoals(self, avId, goals):
        try:
            os.makedirs(os.path.dirname(self.__path(avId)), exist_ok=True)
            with open(self.__path(avId), 'w') as f:
                json.dump(sorted(goals), f)
        except Exception:
            self.notify.warning('could not save the hunt of %s' % avId)

    def avatarAttemptingGoal(self, avId, goal):
        av = self.air.doId2do.get(avId)
        if av is None or goal not in self.GOALS:
            return
        found = self.foundGoals(avId)
        if goal in found:
            if set(found) >= set(self.GOALS):
                self.huntCompletedReward(avId, goal)        # (saying it again once done renews the reward)
            else:
                self.huntGoalAlreadyFound(avId)
            return
        found.append(goal)
        self.__saveGoals(avId, found)
        self.huntGoalFound(avId, goal)
        if set(found) >= set(self.GOALS):
            self.air.writeServerEvent('scavengerHuntDone', avId, self.huntKey())
            taskMgr.doMethodLater(10, lambda task: self.huntCompletedReward(avId, goal, True), 'huntDone-%d' % avId)

    # what a hunt gives (subclasses)
    def huntCompletedReward(self, avId, goal, firstTime=False):
        pass

    def huntGoalAlreadyFound(self, avId):
        pass

    def huntGoalFound(self, avId, goal):
        pass
