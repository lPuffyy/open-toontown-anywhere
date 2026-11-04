from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyCatchActivityAI import DistributedPartyCatchActivityAI


class DistributedPartyWinterCatchActivityAI(DistributedPartyCatchActivityAI):
    """The Catch activity in its holiday look."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyWinterCatchActivityAI')

    def __init__(self, air, partyDoId, x, y, h):
        DistributedPartyCatchActivityAI.__init__(self, air, partyDoId, x, y, h)
        self.activityId = PartyGlobals.ActivityIds.PartyWinterCatch
