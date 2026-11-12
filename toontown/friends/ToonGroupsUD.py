import time
import traceback

from toontown.friends import ToonGroupsGlobals as G


class ToonGroupsUDMixin:
    """The group tracker (the in-game answer to ToonHQ's groups): a toon posts a group for a Cog activity, anyone playing sees the
    list on the Groups page of the sticker book and joins, which takes them to where the host is. Lives inside ToonPresenceUD, which
    knows who is playing (`self.district`) and tells it when a toon is gone. Nothing is saved: groups end with their host."""

    def initGroups(self):
        self.groups = {}                     # group id -> record (a dict, see groupPost)
        self.hostGroup = {}                  # host avId -> group id
        self.memberGroup = {}                # member avId -> group id
        self.groupNext = 1
        self.groupAsked = {}                 # (what, avId) -> when it was last asked
        taskMgr.doMethodLater(G.SWEEP_EVERY, self.__groupSweep, 'toonGroupsSweep')

    # ---- helpers
    def __limited(self, what, avId, interval):
        now = time.time()
        if now - self.groupAsked.get((what, avId), 0.0) < interval:
            return True
        self.groupAsked[(what, avId)] = now
        if len(self.groupAsked) > 4000:
            self.groupAsked = {k: t for k, t in self.groupAsked.items() if now - t < 60.0}
        return False

    def __result(self, avId, op, code, group=None):
        gid, shard, hood, zone = (group['id'], group['shard'], group['hood'], group['zone']) if group else (0, 0, 0, 0)
        self.sendUpdateToAvatarId(avId, 'groupResult', [op, code, gid, shard, hood, zone])

    @staticmethod
    def __uint(value):
        try:
            return max(0, min(int(value), 0xFFFFFFFF))
        except (TypeError, ValueError):
            return 0

    def __size(self, group):
        return 1 + len(group['members'])

    def __removeGroup(self, group, tellMembers=True):
        self.groups.pop(group['id'], None)
        self.hostGroup.pop(group['host'], None)
        for m in list(group['members']):
            self.memberGroup.pop(m, None)
            if tellMembers and m in self.district:
                self.__result(m, G.OP_CLOSED, G.OK, group)
        group['members'].clear()

    def __leave(self, avId, tellHost=False):
        """avId stops hosting or being a member of whatever group it is in."""
        gid = self.hostGroup.get(avId)
        if gid in self.groups:
            self.__removeGroup(self.groups[gid])
        self.hostGroup.pop(avId, None)
        gid = self.memberGroup.pop(avId, None)
        group = self.groups.get(gid)
        if group:
            group['members'].discard(avId)

    # ---- from a toon that stopped playing (called by ToonPresenceUD once its grace time is over)
    def groupsToonGone(self, avId):
        self.__leave(avId)

    def __groupSweep(self, task):
        try:
            now = time.time()
            for group in list(self.groups.values()):
                if now - group['seen'] > G.STALE:
                    self.notify.info('group %s of toon %s expired' % (group['id'], group['host']))
                    self.__removeGroup(group)
                else:
                    for m in [m for m in group['members'] if m not in self.district and m not in self.online]:
                        group['members'].discard(m)
                        self.memberGroup.pop(m, None)
        except Exception:
            self.notify.warning('group sweep failed: %s' % traceback.format_exc())
        return task.again

    # ---- from the clients
    def groupPost(self, kind, maxSize, shard, hood, zone):
        avId = self.air.getAvatarIdFromSender()
        if not avId or avId not in self.district:
            return
        if self.__limited('post', avId, G.POST_COOLDOWN):
            return self.__result(avId, G.OP_POST, G.BUSY)
        if kind not in G.KINDS:
            return self.__result(avId, G.OP_POST, G.BAD)
        if len(self.groups) >= G.MAX_GROUPS:
            return self.__result(avId, G.OP_POST, G.FULL)
        maxSize = max(G.MIN_SIZE, min(maxSize, G.MAX_SIZE))
        self.__leave(avId)

        def refuse():
            self.__result(avId, G.OP_POST, G.BAD)

        def named(dclass, fields):
            # the host's name comes from the database, never from the client
            try:
                value = fields.get('setName') if fields else None
                if not value or not value[0]:
                    return refuse()
                if avId not in self.district or avId in self.hostGroup:
                    return
                now = time.time()
                group = {'id': self.groupNext, 'host': avId, 'name': str(value[0])[:24], 'kind': kind, 'max': maxSize,
                         'shard': self.__uint(shard), 'hood': self.__uint(hood), 'zone': self.__uint(zone),
                         'members': set(), 'born': now, 'seen': now}
                self.groupNext = self.groupNext % 0x7FFFFFFF + 1
                self.groups[group['id']] = group
                self.hostGroup[avId] = group['id']
                self.notify.info('toon %s posted group %s (kind %s)' % (avId, group['id'], kind))
                self.__result(avId, G.OP_POST, G.OK, group)
            except Exception:
                self.notify.warning('could not post a group for toon %s: %s' % (avId, traceback.format_exc()))
                refuse()
        try:
            self.air.dbInterface.queryObject(self.air.dbId, avId, named)
        except Exception:
            self.notify.warning('could not ask the database for toon %s: %s' % (avId, traceback.format_exc()))
            refuse()

    def groupMove(self, shard, hood, zone):
        """The host's client says where it is (every HEARTBEAT seconds): joiners are sent there, and the group stays alive."""
        avId = self.air.getAvatarIdFromSender()
        group = self.groups.get(self.hostGroup.get(avId))
        if not group or self.__limited('move', avId, G.MOVE_COOLDOWN):
            return
        if shard or hood:                    # zeros mean "no place to report right now" (in a battle): keep the last one
            group['shard'], group['hood'], group['zone'] = self.__uint(shard), self.__uint(hood), self.__uint(zone)
        group['seen'] = time.time()

    def groupDisband(self):
        avId = self.air.getAvatarIdFromSender()
        group = self.groups.get(self.hostGroup.get(avId))
        if group:
            self.__removeGroup(group)
        self.__result(avId, G.OP_LEAVE, G.OK)

    def groupLeave(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.hostGroup:
            return self.groupDisband()
        self.__leave(avId)
        self.__result(avId, G.OP_LEAVE, G.OK)

    def groupJoin(self, groupId):
        avId = self.air.getAvatarIdFromSender()
        if not avId or avId not in self.district:
            return
        if self.__limited('join', avId, G.JOIN_COOLDOWN):
            return self.__result(avId, G.OP_JOIN, G.BUSY)
        group = self.groups.get(groupId)
        if not group:
            return self.__result(avId, G.OP_JOIN, G.GONE)
        if group['host'] == avId:
            return self.__result(avId, G.OP_JOIN, G.OWN, group)
        if self.memberGroup.get(avId) != groupId:
            if self.__size(group) >= group['max']:
                return self.__result(avId, G.OP_JOIN, G.FULL, group)
            self.__leave(avId)
            group['members'].add(avId)
            self.memberGroup[avId] = groupId
        self.__result(avId, G.OP_JOIN, G.OK, group)

    def groupListRequest(self):
        avId = self.air.getAvatarIdFromSender()
        if not avId or self.__limited('list', avId, G.LIST_COOLDOWN):
            return
        now = time.time()
        newest = sorted(self.groups.values(), key=lambda g: g['born'], reverse=True)[:G.LIST_LIMIT]
        mine = self.hostGroup.get(avId) or self.memberGroup.get(avId) or 0
        self.sendUpdateToAvatarId(avId, 'groupList', [
            mine,
            [g['id'] for g in newest], [g['kind'] for g in newest], [g['name'] for g in newest],
            [self.__size(g) for g in newest], [g['max'] for g in newest],
            [g['shard'] for g in newest], [g['hood'] for g in newest],
            [min(int(now - g['born']), 0xFFFF) for g in newest]])
