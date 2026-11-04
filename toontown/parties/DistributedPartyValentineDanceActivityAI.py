from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyDanceActivityAI import DistributedPartyDanceActivityAI


class DistributedPartyValentineDanceActivityAI(DistributedPartyDanceActivityAI):
    """The Dance activity in its holiday look."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyValentineDanceActivityAI')

    def __init__(self, air, partyDoId, x, y, h):
        DistributedPartyDanceActivityAI.__init__(self, air, partyDoId, x, y, h)
        self.activityId = PartyGlobals.ActivityIds.PartyValentineDance
