from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalAI import DistributedObjectGlobalAI


class ToonPresenceAI(DistributedObjectGlobalAI):
    """A district's line to the UberDOG's ToonPresence: tell it when toons arrive, leave or make friends."""
    notify = DirectNotifyGlobal.directNotify.newCategory('ToonPresenceAI')
