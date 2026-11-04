from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.parties import PartyGlobals


class DistributedPartyGateAI(DistributedObjectAI):
    """The party gate in a playground (from the original game): lists the public parties going on in every district and sends a
    toon to the one they pick."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyGateAI')

    def getPartyList(self, avId):
        if avId != self.air.getAvatarIdFromSender():
            return
        self.sendUpdateToAvatarId(avId, 'listAllPublicParties', [self.air.partyManager.getAllPublicParties()])

    def partyChoiceRequest(self, avId, shardId, zoneId):
        if avId != self.air.getAvatarIdFromSender():
            return
        for party in self.air.partyManager.getAllPublicParties():
            if party[0] == shardId and party[1] == zoneId:
                if party[2] < PartyGlobals.MaxToonsAtAParty:
                    self.sendUpdateToAvatarId(avId, 'setParty', [party])
                else:
                    self.sendUpdateToAvatarId(avId, 'partyRequestDenied', [PartyGlobals.PartyGateDenialReasons.Full])
                return
        self.sendUpdateToAvatarId(avId, 'partyRequestDenied', [PartyGlobals.PartyGateDenialReasons.Unavailable])
