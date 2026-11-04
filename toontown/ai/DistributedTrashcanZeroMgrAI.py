from direct.directnotify import DirectNotifyGlobal
from toontown.ai.DistributedPhaseEventMgrAI import DistributedPhaseEventMgrAI


class DistributedTrashcanZeroMgrAI(DistributedPhaseEventMgrAI):
    """Trashcan Zero, the street prop that wakes up first: which of his moves the clients play."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrashcanZeroMgrAI')
