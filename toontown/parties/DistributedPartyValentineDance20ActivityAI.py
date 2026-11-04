from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyDance20ActivityAI import DistributedPartyDance20ActivityAI


class DistributedPartyValentineDance20ActivityAI(DistributedPartyDance20ActivityAI):
    """The Dance20 activity in its holiday look."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyValentineDance20ActivityAI')

    def __init__(self, air, partyDoId, x, y, h):
        DistributedPartyDance20ActivityAI.__init__(self, air, partyDoId, x, y, h)
        self.activityId = PartyGlobals.ActivityIds.PartyValentineDance20
