from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyJukeboxActivityAI import DistributedPartyJukeboxActivityAI


class DistributedPartyValentineJukeboxActivityAI(DistributedPartyJukeboxActivityAI):
    """The Jukebox activity in its holiday look."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyValentineJukeboxActivityAI')

    def __init__(self, air, partyDoId, x, y, h):
        DistributedPartyJukeboxActivityAI.__init__(self, air, partyDoId, x, y, h)
        self.activityId = PartyGlobals.ActivityIds.PartyValentineJukebox
