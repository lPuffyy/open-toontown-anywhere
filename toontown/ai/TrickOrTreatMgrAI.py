import time
from direct.directnotify import DirectNotifyGlobal
from otp.otpbase import OTPGlobals
from toontown.ai.ScavengerHuntMgrAI import ScavengerHuntMgrAI
from toontown.toonbase import ToontownGlobals

REWARD_MINUTES = 7 * 24 * 60      # the pumpkin head lasts a week (the original: until the holiday ended)


class TrickOrTreatMgrAI(ScavengerHuntMgrAI):
    """Trick-or-Treat (from the original game): say "Trick or Treat!" in one shop in each playground's streets. Each pays jelly
    beans; all six give a pumpkin head."""
    notify = DirectNotifyGlobal.directNotify.newCategory('TrickOrTreatMgrAI')
    huntName = 'trick_or_treat'
    GOALS = {0: 2649,    # Toontown Central
             1: 1834,    # Donald's Dock
             2: 4835,    # Minnie's Melodyland
             3: 5620,    # Daisy Gardens
             4: 3707,    # The Brrrgh
             5: 9619}    # Donald's Dreamland

    def targetClass(self):
        from toontown.ai.DistributedTrickOrTreatTargetAI import DistributedTrickOrTreatTargetAI
        return DistributedTrickOrTreatTargetAI

    def huntCompletedReward(self, avId, goal, firstTime=False):
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.b_setCheesyEffect(OTPGlobals.CEPumpkin, 0, int(time.time() / 60) + REWARD_MINUTES)

    def huntGoalAlreadyFound(self, avId):
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.sendUpdate('trickOrTreatTargetMet', [0])

    def huntGoalFound(self, avId, goal):
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.addMoney(ToontownGlobals.TOT_REWARD_JELLYBEAN_AMOUNT)
            av.sendUpdate('trickOrTreatTargetMet', [ToontownGlobals.TOT_REWARD_JELLYBEAN_AMOUNT])
