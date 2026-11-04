import time
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from otp.otpbase import OTPGlobals

EFFECT = OTPGlobals.CEBigWhite
DURATION = 60          # minutes
HOOD = 3000


class DistributedPolarPlaceEffectMgrAI(DistributedObjectAI):
    """The Polar Place event (from the original game): sits in Hibernation Vacations, and a toon who says "Howdy!" to Paula
    Behr there turns big and white in The Brrrgh for an hour."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPolarPlaceEffectMgrAI')

    def addPolarPlaceEffect(self):
        av = self.air.doId2do.get(self.air.getAvatarIdFromSender())
        if av is not None and av.zoneId == self.zoneId:
            av.b_setCheesyEffect(EFFECT, HOOD, int(time.time() / 60 + 0.5) + DURATION)
