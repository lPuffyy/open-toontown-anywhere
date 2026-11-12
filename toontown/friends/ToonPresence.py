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

    def up_requestAvatarDetails(self, avId):
        self.sendUpdate('requestAvatarDetails', [avId])

    def up_requestPetDetails(self, petId):
        self.sendUpdate('requestPetDetails', [petId])

    # ---- the group tracker (the Groups page of the sticker book, toontown/shtiker/GroupsPage.py)
    def up_groupPost(self, kind, maxSize):
        where = self.groupLocation()
        if where is None:
            return False
        self.sendUpdate('groupPost', [kind, maxSize] + list(where))
        return True

    def up_groupJoin(self, groupId):
        self.sendUpdate('groupJoin', [groupId])

    def up_groupLeave(self):
        self.sendUpdate('groupLeave', [])

    def up_groupDisband(self):
        self.sendUpdate('groupDisband', [])

    def up_groupListRequest(self):
        self.sendUpdate('groupListRequest', [])

    def groupLocation(self):
        """(district, hood, zone) of where this toon is now, in the form Go To uses, or None when it is not somewhere it can be found."""
        try:
            place = base.cr.playGame.getPlace()
            return (base.localAvatar.defaultShard, base.cr.playGame.getPlaceId(), place.getZoneId())
        except Exception:
            return None

    def groupResult(self, op, code, groupId, shard, hood, zone):
        from toontown.friends import ToonGroupsGlobals as G
        if op == G.OP_POST and code == G.OK:
            self.hostedGroupId = groupId
            self.__startGroupHeartbeat()
        elif op in (G.OP_CLOSED, G.OP_LEAVE):
            self.hostedGroupId = None
            self.__stopGroupHeartbeat()
        messenger.send('toonGroupResult', [op, code, groupId, shard, hood, zone])

    def groupList(self, mine, ids, kinds, names, sizes, maxes, shards, hoods, ages):
        groups = []
        for i in range(len(ids)):
            groups.append({'id': ids[i], 'kind': kinds[i], 'name': names[i], 'size': sizes[i], 'max': maxes[i],
                           'shard': shards[i], 'hood': hoods[i], 'age': ages[i]})
        messenger.send('toonGroupList', [mine, groups])

    def __startGroupHeartbeat(self):
        from toontown.friends import ToonGroupsGlobals as G
        taskMgr.remove('toonGroupHeartbeat')
        taskMgr.doMethodLater(G.HEARTBEAT, self.__groupHeartbeat, 'toonGroupHeartbeat')

    def __stopGroupHeartbeat(self):
        taskMgr.remove('toonGroupHeartbeat')

    def __groupHeartbeat(self, task):
        if not hasattr(base, 'localAvatar') or base.localAvatar is None:
            return task.done
        # in a battle or an elevator there is no place to report: zeros keep the last place and only show the host is still here
        self.sendUpdate('groupMove', list(self.groupLocation() or (0, 0, 0)))
        return task.again

    # ---- from the server
    def avatarDetailsResponse(self, avId, code, experience, inventory, trackAccess, maxHp, hp, shard, lastHood):
        base.cr.handleAvatarDetailsResponse(avId, code, experience, inventory, trackAccess, maxHp, hp, shard, lastHood)

    def petDetailsResponse(self, petId, code, name, look):
        base.cr.handlePetDetailsResponse(petId, code, name, look)

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
