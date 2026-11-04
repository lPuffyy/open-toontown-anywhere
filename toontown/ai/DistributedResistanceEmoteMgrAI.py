from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

RESISTANCE_EMOTE = 15


class DistributedResistanceEmoteMgrAI(DistributedObjectAI):
    """The Resistance event (from the original game): sits in Talking in Your Sleep Voiceover Training, and a toon who says "Do
    you need help?" to Whispering Willow there learns the Resistance salute."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedResistanceEmoteMgrAI')

    def addResistanceEmote(self):
        av = self.air.doId2do.get(self.air.getAvatarIdFromSender())
        if av is not None and av.zoneId == self.zoneId:
            av.setEmoteAccessId(RESISTANCE_EMOTE, 1)
