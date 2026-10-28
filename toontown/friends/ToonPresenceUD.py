import json
import os
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD


class ToonPresenceUD(DistributedObjectGlobalUD):
    """Knows which toons are playing, in any district, and carries the messages that must reach a toon in another district:
    a friend coming or going, and the Go To (teleport to a friend) questions and answers. Each district's AI tells it when a
    toon arrives or leaves; a client can only ask it to pass a Go To message on to a friend."""
    notify = DirectNotifyGlobal.directNotify.newCategory('ToonPresenceUD')
    STATUS_FILE = '/ot/data/online.json'          # who is playing, for the Discord status script (counts only)
    STATUS_EVERY = 30.0

    def __init__(self, air):
        DistributedObjectGlobalUD.__init__(self, air)
        self.online = {}                    # avId -> set of that toon's friends' avIds
        self.district = {}                  # avId -> name of the district the toon is in
        taskMgr.doMethodLater(self.STATUS_EVERY, self.__writeStatus, 'toonPresenceStatus')

    def __writeStatus(self, task):
        """Write how many toons are playing (in total and in each district) for the Discord status script. Counts only, no names."""
        try:
            counts = {}
            for avId in self.online:
                name = self.district.get(avId, '') or 'Unknown'
                counts[name] = counts.get(name, 0) + 1
            data = {'updated': int(time.time()), 'total': len(self.online), 'districts': counts}
            tmp = self.STATUS_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(data, f)
            os.replace(tmp, self.STATUS_FILE)
        except Exception:
            self.notify.warning('could not write the status file')
        return task.again

    # ---- from the districts
    def avatarOnline(self, avId, friends, districtName):
        if self.online.get(avId) == set(friends) and self.district.get(avId) == districtName:
            return                       # already known (the districts repeat this every minute to keep the list true)
        self.notify.info('toon %s is playing in %s' % (avId, districtName))
        self.online[avId] = set(friends)
        self.district[avId] = districtName
        for friendId in friends:
            if friendId in self.online:
                self.sendUpdateToAvatarId(friendId, 'friendOnline', [avId, 1])
                self.sendUpdateToAvatarId(avId, 'friendOnline', [friendId, 1])

    def avatarOffline(self, avId, districtName):
        if avId not in self.online or self.district.get(avId) != districtName:
            return                       # the toon already arrived in another district: this is the old district catching up
        self.notify.info('toon %s left %s' % (avId, districtName))
        friends = self.online.pop(avId, set())
        self.district.pop(avId, None)
        for friendId in friends:
            if friendId in self.online:
                self.sendUpdateToAvatarId(friendId, 'friendOnline', [avId, 0])

    def districtSweep(self, districtName, avIds):
        """A district's full list of its toons, sent every minute: anyone we think is in that district but is not on the list left."""
        here = set(avIds)
        for avId in [a for a, d in self.district.items() if d == districtName and a not in here]:
            self.avatarOffline(avId, districtName)

    def friendshipMade(self, avIdA, avIdB):
        for me, other in ((avIdA, avIdB), (avIdB, avIdA)):
            if me in self.online:
                self.online[me].add(other)
        if avIdA in self.online and avIdB in self.online:
            self.sendUpdateToAvatarId(avIdA, 'friendOnline', [avIdB, 1])
            self.sendUpdateToAvatarId(avIdB, 'friendOnline', [avIdA, 1])

    # ---- ending a friendship: the other toon's phone is told, and asks its own district to forget the friend
    def relayRemoveFriend(self, toAvId):
        fromAvId = self.air.getAvatarIdFromSender()
        if fromAvId in self.online:
            self.online[fromAvId].discard(toAvId)
        if toAvId in self.online:
            self.online[toAvId].discard(fromAvId)
            self.sendUpdateToAvatarId(toAvId, 'friendRemoved', [fromAvId])

    # ---- Go To: a toon asks a friend (in any district) if it can come to them
    def __friends(self, a, b):
        """True when a and b are both playing and b has a as a friend."""
        return a in self.online and b in self.online and a in self.online[b]

    def relayTeleportQuery(self, toAvId):
        fromAvId = self.air.getAvatarIdFromSender()
        if self.__friends(fromAvId, toAvId):
            self.sendUpdateToAvatarId(toAvId, 'teleportQueryFrom', [fromAvId])
        else:
            # not playing, or not a friend: the asker is told it cannot be done
            self.sendUpdateToAvatarId(fromAvId, 'teleportResponseFrom', [toAvId, 0, 0, 0, 0])

    def relayTeleportResponse(self, toAvId, available, shardId, hoodId, zoneId):
        fromAvId = self.air.getAvatarIdFromSender()
        if self.__friends(fromAvId, toAvId):
            self.sendUpdateToAvatarId(toAvId, 'teleportResponseFrom', [fromAvId, available, shardId, hoodId, zoneId])

    def relayTeleportGiveup(self, toAvId):
        fromAvId = self.air.getAvatarIdFromSender()
        if self.__friends(fromAvId, toAvId):
            self.sendUpdateToAvatarId(toAvId, 'teleportGiveupFrom', [fromAvId])
