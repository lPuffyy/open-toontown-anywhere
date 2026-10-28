from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobal import DistributedObjectGlobal


class ToonPresence(DistributedObjectGlobal):
    """The client's line to the UberDOG's ToonPresence. The server cannot let one client send a message straight to a toon the
    client cannot see, so Go To questions and answers go through here, and friends coming and going arrive from here."""
    notify = DirectNotifyGlobal.directNotify.newCategory('ToonPresence')

    # ---- to the server
    def up_teleportQuery(self, toAvId):
        self.sendUpdate('relayTeleportQuery', [toAvId])

    def up_teleportResponse(self, toAvId, available, shardId, hoodId, zoneId):
        self.sendUpdate('relayTeleportResponse', [toAvId, available, shardId, hoodId, zoneId])

    def up_teleportGiveup(self, toAvId):
        self.sendUpdate('relayTeleportGiveup', [toAvId])

    def up_removeFriend(self, toAvId):
        self.sendUpdate('relayRemoveFriend', [toAvId])

    # ---- from the server
    def friendOnline(self, friendId, online):
        if hasattr(base, 'localAvatar'):
            base.localAvatar.setFriendOnline(friendId, online)

    def friendRemoved(self, fromAvId):
        """A friend ended the friendship: forget them here too (our own district drops them from the saved list)."""
        if hasattr(base, 'localAvatar'):
            base.localAvatar.sendUpdate('removeFriend', [fromAvId])
            for pair in list(base.localAvatar.friendsList):
                if pair[0] == fromAvId:
                    base.localAvatar.friendsList.remove(pair)
            base.cr.friendsOnline.pop(fromAvId, None)
            try:
                base.localAvatar.friendsNotify(fromAvId, 1)
            except Exception:
                pass
            messenger.send('friendsListChanged')

    def teleportQueryFrom(self, requesterId):
        if hasattr(base, 'localAvatar'):
            base.localAvatar.teleportQuery(requesterId)

    def teleportResponseFrom(self, avId, available, shardId, hoodId, zoneId):
        if hasattr(base, 'localAvatar'):
            base.localAvatar.teleportResponse(avId, available, shardId, hoodId, zoneId)

    def teleportGiveupFrom(self, requesterId):
        if hasattr(base, 'localAvatar'):
            base.localAvatar.teleportGiveup(requesterId)
