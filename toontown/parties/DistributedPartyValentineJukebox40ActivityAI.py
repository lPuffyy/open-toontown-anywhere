from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyJukebox40ActivityAI import DistributedPartyJukebox40ActivityAI


class DistributedPartyValentineJukebox40ActivityAI(DistributedPartyJukebox40ActivityAI):
    """The Jukebox40 activity in its holiday look."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyValentineJukebox40ActivityAI')

    def __init__(self, air, partyDoId, x, y, h):
        DistributedPartyJukebox40ActivityAI.__init__(self, air, partyDoId, x, y, h)
        self.activityId = PartyGlobals.ActivityIds.PartyValentineJukebox40
