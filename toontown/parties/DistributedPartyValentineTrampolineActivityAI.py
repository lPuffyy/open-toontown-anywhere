from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyTrampolineActivityAI import DistributedPartyTrampolineActivityAI


class DistributedPartyValentineTrampolineActivityAI(DistributedPartyTrampolineActivityAI):
    """The Trampoline activity in its holiday look."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyValentineTrampolineActivityAI')

    def __init__(self, air, partyDoId, x, y, h):
        DistributedPartyTrampolineActivityAI.__init__(self, air, partyDoId, x, y, h)
        self.activityId = PartyGlobals.ActivityIds.PartyValentineTrampoline
