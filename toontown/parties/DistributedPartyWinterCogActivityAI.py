from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyCogActivityAI import DistributedPartyCogActivityAI


class DistributedPartyWinterCogActivityAI(DistributedPartyCogActivityAI):
    """The Cog activity in its holiday look."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyWinterCogActivityAI')

    def __init__(self, air, partyDoId, x, y, h):
        DistributedPartyCogActivityAI.__init__(self, air, partyDoId, x, y, h)
        self.activityId = PartyGlobals.ActivityIds.PartyWinterCog
