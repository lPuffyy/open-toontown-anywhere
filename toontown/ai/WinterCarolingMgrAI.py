import time
from direct.directnotify import DirectNotifyGlobal
from otp.otpbase import OTPGlobals
from toontown.ai.ScavengerHuntMgrAI import ScavengerHuntMgrAI
from toontown.toonbase import ToontownGlobals

REWARD_MINUTES = 14 * 24 * 60     # the snowman head lasts two weeks (the original: until the holiday ended)


class WinterCarolingMgrAI(ScavengerHuntMgrAI):
    """Winter caroling (from the original game): sing a carol in one shop in each playground's streets. Each pays jelly beans;
    all six give a snowman head."""
    notify = DirectNotifyGlobal.directNotify.newCategory('WinterCarolingMgrAI')
    huntName = 'winter_caroling'
    GOALS = {0: 2659,    # Joy Buzzers to the World, Silly Street
             1: 1707,    # Gifts With A Porpoise, Seaweed Street
             2: 5626,    # Pine Needle Crafts, Elm Street
             3: 4614,    # Shave and a Haircut for a Song, Alto Avenue
             4: 3828,    # Snowman's Land, Polar Place
             5: 9720}    # Talking in Your Sleep Voice Training, Pajama Place

    def targetClass(self):
        from toontown.ai.DistributedWinterCarolingTargetAI import DistributedWinterCarolingTargetAI
        return DistributedWinterCarolingTargetAI

    def startsLateInYear(self):
        return True

    def huntCompletedReward(self, avId, goal, firstTime=False):
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.b_setCheesyEffect(OTPGlobals.CESnowMan, 0, int(time.time() / 60) + REWARD_MINUTES)

    def huntGoalAlreadyFound(self, avId):
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.sendUpdate('winterCarolingTargetMet', [0])

    def huntGoalFound(self, avId, goal):
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.addMoney(ToontownGlobals.TOT_REWARD_JELLYBEAN_AMOUNT)
            av.sendUpdate('winterCarolingTargetMet', [ToontownGlobals.TOT_REWARD_JELLYBEAN_AMOUNT])
