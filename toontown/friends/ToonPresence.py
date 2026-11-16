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

    def up_whisper(self, toAvId, kind, value, text=''):
        self.sendUpdate('relayWhisper', [toAvId, kind, value, text])

    def up_requestAvatarDetails(self, avId):
        self.sendUpdate('requestAvatarDetails', [avId])

    def up_requestPetDetails(self, petId):
        self.sendUpdate('requestPetDetails', [petId])

    # ---- the group tracker (the Groups page of the sticker book, toontown/shtiker/GroupsPage.py)
    def up_groupPost(self, kind, maxSize, sub=0, friendsOnly=False, looking=0):
        from toontown.friends import ToonGroupsGlobals as G
        where = self.groupLocation()
        if where is None:
            return False
        self.sendUpdate('groupPost', [G.packKind(kind, sub), G.packSize(maxSize, friendsOnly, looking)] + list(where))
        return True

    def up_groupJoin(self, groupId):
        self.sendUpdate('groupJoin', [groupId])

    def up_groupLeave(self):
        self.sendUpdate('groupLeave', [])

    def up_groupDisband(self):
        self.sendUpdate('groupDisband', [])

    def up_groupListRequest(self):
        self.sendUpdate('groupListRequest', [])

    def __groupPlace(self):
        """(district, hood, zone, inside): where this toon is, and whether it is inside something (a building, a factory, a boss fight, an
        elevator) where nobody can be taken to it: a zone made for the activity, or an interior. None when it has no place at all."""
        try:
            place = base.cr.playGame.getPlace()
            shard, hood, zone = base.localAvatar.defaultShard, base.cr.playGame.getPlaceId(), place.getZoneId()
        except Exception:
            return None
        if not shard or not hood or not zone:
            return None
        inside = False
        try:
            from toontown.hood import ZoneUtil
            if ZoneUtil.isDynamicZone(zone) or ZoneUtil.getWhereName(zone, 1) not in ('playground', 'street', 'cogHQExterior', 'cogHQLobby', 'factoryExterior'):
                inside = True
            state = place.fsm.getCurrentState().getName() if getattr(place, 'fsm', None) else ''
            if state in ('elevator', 'elevatorOut', 'elevatorIn'):
                inside = True
        except Exception:
            inside = True
        return (shard, hood, zone, inside)

    def groupLocation(self):
        """(district, hood, zone) of where this toon is now, in the form Go To uses, or None when it is not somewhere it can be found
        (or is inside an activity)."""
        where = self.__groupPlace()
        if where is None or where[3]:
            return None
        return where[:3]

    def __groupReport(self):
        """What the host tells the server: the place, or (district, 0, 0) when inside its activity, or zeros when it has no place."""
        where = self.__groupPlace()
        if where is None:
            return (0, 0, 0)
        return (where[0], 0, 0) if where[3] else where[:3]

    def __announceRoster(self, mine, groups):
        """Say who joined or left the group this toon is in (the host and every member are told when the list changes)."""
        try:
            group = next((g for g in groups if g['id'] == mine), None) if mine else None
            if group is None:
                self.rosterGroup = None
                return
            roster = [group['name']] + list(group['members'])
            if getattr(self, 'rosterGroup', None) == mine:
                me = base.localAvatar.getName()
                old = getattr(self, 'rosterNames', [])
                from toontown.toonbase import TTLocalizer
                for name in roster:
                    if name not in old and name != me:
                        base.localAvatar.setSystemMessage(0, TTLocalizer.GroupsPageJoinedNotice % name)
                for name in old:
                    if name not in roster and name != me:
                        base.localAvatar.setSystemMessage(0, TTLocalizer.GroupsPageLeftNotice % name)
            self.rosterGroup = mine
            self.rosterNames = roster
        except Exception:
            self.notify.warning('could not announce the group roster', exc_info=True)

    def groupResult(self, op, code, groupId, shard, hood, zone):
        from toontown.friends import ToonGroupsGlobals as G
        if op == G.OP_POST and code == G.OK:
            self.hostedGroupId = groupId
            self.__startGroupHeartbeat()
        elif op in (G.OP_CLOSED, G.OP_LEAVE):
            self.hostedGroupId = None
            self.rosterGroup = None
            self.__stopGroupHeartbeat()
        elif op == G.OP_MEMBERS:
            self.up_groupListRequest()           # someone joined or left: the new list says who
            return
        messenger.send('toonGroupResult', [op, code, groupId, shard, hood, zone])

    def groupList(self, mine, ids, kinds, names, sizes, maxes, shards, hoods, ages):
        from toontown.friends import ToonGroupsGlobals as G
        groups = []
        for i in range(len(ids)):
            kind, sub = G.unpackKind(kinds[i])
            maxSize, friendsOnly, looking = G.unpackSize(maxes[i])
            parts = names[i].split(G.NAME_SEP)
            groups.append({'id': ids[i], 'kind': kind, 'sub': sub, 'name': parts[0], 'members': parts[1:], 'size': sizes[i], 'max': maxSize,
                           'friends': friendsOnly, 'looking': looking, 'started': G.isStarted(maxes[i]),
                           'shard': shards[i], 'hood': hoods[i], 'age': ages[i]})
        self.__announceRoster(mine, groups)
        messenger.send('toonGroupList', [mine, groups])

    def __startGroupHeartbeat(self):
        from toontown.friends import ToonGroupsGlobals as G
        taskMgr.remove('toonGroupHeartbeat')
        taskMgr.remove('toonGroupWatch')
        self.groupReported = None
        taskMgr.doMethodLater(G.HEARTBEAT, self.__groupHeartbeat, 'toonGroupHeartbeat')
        taskMgr.doMethodLater(G.WATCH_EVERY, self.__groupWatch, 'toonGroupWatch')

    def __stopGroupHeartbeat(self):
        taskMgr.remove('toonGroupHeartbeat')
        taskMgr.remove('toonGroupWatch')

    def __groupWatch(self, task):
        """The host went inside (or came out): say so at once, so nobody is sent in after it."""
        if not hasattr(base, 'localAvatar') or base.localAvatar is None:
            return task.done
        where = self.__groupReport()
        if where != getattr(self, 'groupReported', None):
            self.groupReported = where
            self.sendUpdate('groupMove', list(where))
        return task.again

    def __groupHeartbeat(self, task):
        if not hasattr(base, 'localAvatar') or base.localAvatar is None:
            return task.done
        # in a battle or an elevator there is no place to report: zeros keep the last place and only show the host is still here
        self.groupReported = self.__groupReport()
        self.sendUpdate('groupMove', list(self.groupReported))
        return task.again

    # ---- from the server
    def whisperFrom(self, fromId, kind, value, text):
        """A friend who is not in view whispered to us (see ToonPresenceUD.relayWhisper)."""
        if not hasattr(base, 'localAvatar') or base.localAvatar is None:
            return
        la = base.localAvatar
        if kind == 0:
            la.setTalkWhisper(fromId, 0, '', text, [], 0)
        elif kind == 1:
            la.setWhisperSCFrom(fromId, value)
        elif kind == 2:
            la.setWhisperSCCustomFrom(fromId, value)
        elif kind == 3:
            la.setWhisperSCEmoteFrom(fromId, value)

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
