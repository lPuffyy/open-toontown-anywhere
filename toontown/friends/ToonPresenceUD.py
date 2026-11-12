import json
import os
import time
import traceback

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD
from toontown.friends.ToonGroupsUD import ToonGroupsUDMixin


class ToonPresenceUD(DistributedObjectGlobalUD, ToonGroupsUDMixin):
    """Knows which toons are playing, in any district, and carries the messages that must reach a toon in another district:
    a friend coming or going, and the Go To (teleport to a friend) questions and answers. Each district's AI tells it when a
    toon arrives or leaves; a client can only ask it to pass a Go To message on to a friend."""
    notify = DirectNotifyGlobal.directNotify.newCategory('ToonPresenceUD')
    STATUS_FILE = '/ot/data/online.json'          # who is playing, for the Discord status script (counts only)
    STATUS_EVERY = 30.0

    def __init__(self, air):
        DistributedObjectGlobalUD.__init__(self, air)
        self.online = {}                    # avId -> set of that toon's friends' avIds (kept a moment after it leaves, see LEFT_GRACE)
        self.district = {}                  # avId -> name of the district the toon is in: the toons playing right now
        self.detailsAsked = {}              # avId of a client -> when it last asked for a toon's details
        taskMgr.doMethodLater(self.STATUS_EVERY, self.__writeStatus, 'toonPresenceStatus')
        self.initGroups()                   # the group tracker (ToonGroupsUD.py)

    def __writeStatus(self, task):
        """Write how many toons are playing (in total and in each district) for the Discord status script. Counts only, no names."""
        try:
            counts = {}
            for avId in self.district:
                name = self.district[avId] or 'Unknown'
                counts[name] = counts.get(name, 0) + 1
            data = {'updated': int(time.time()), 'total': len(self.district), 'districts': counts}
            tmp = self.STATUS_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(data, f)
            os.replace(tmp, self.STATUS_FILE)
        except Exception:
            self.notify.warning('could not write the status file')
        return task.again

    # ---- from the districts
    # A toon changing district (or going through Go To) leaves its old district a moment before the new one reports it,
    # so its friends are told it left only if it has not turned up again by then.
    LEFT_GRACE = 15.0

    def avatarOnline(self, avId, friends, districtName):
        if self.online.get(avId) == set(friends) and self.district.get(avId) == districtName:
            return                       # already known (the districts repeat this every minute to keep the list true)
        self.notify.info('toon %s is playing in %s' % (avId, districtName))
        returning = taskMgr.hasTaskNamed(self.__leftTask(avId))
        taskMgr.remove(self.__leftTask(avId))
        known = self.online.get(avId, set())
        self.online[avId] = set(friends)
        self.district[avId] = districtName
        for friendId in friends:
            if friendId in self.district and not (returning and friendId in known):
                self.sendUpdateToAvatarId(friendId, 'friendOnline', [avId, 1])
                self.sendUpdateToAvatarId(avId, 'friendOnline', [friendId, 1])

    def avatarOffline(self, avId, districtName):
        if avId not in self.online or self.district.get(avId) != districtName:
            return                       # the toon already arrived in another district: this is the old district catching up
        self.notify.info('toon %s left %s' % (avId, districtName))
        self.district.pop(avId, None)
        # keep its friends (for when it turns up again) but stop Go To and the counts until then
        taskMgr.doMethodLater(self.LEFT_GRACE, self.__toldLeft, self.__leftTask(avId), extraArgs=[avId])

    @staticmethod
    def __leftTask(avId):
        return 'toonPresenceLeft-%d' % avId

    def __toldLeft(self, avId):
        if avId in self.district:
            return                       # it came back
        self.groupsToonGone(avId)
        friends = self.online.pop(avId, set())
        for friendId in friends:
            if friendId in self.district:
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
        if avIdA in self.district and avIdB in self.district:
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
        return a in self.district and b in self.district and a in self.online.get(b, ())

    # ---- another toon's details, for the toon details panel: read from the database, whether or not that toon is playing
    DETAILS_COOLDOWN = 0.5               # seconds a client must wait between two requests

    def requestAvatarDetails(self, avId):
        asker = self.air.getAvatarIdFromSender()
        if not asker or not avId:
            return
        now = time.time()
        if now - self.detailsAsked.get(asker, 0.0) < self.DETAILS_COOLDOWN:
            return
        self.detailsAsked[asker] = now
        if len(self.detailsAsked) > 500:
            self.detailsAsked = {a: t for a, t in self.detailsAsked.items() if now - t < 10.0}

        def refuse():
            self.sendUpdateToAvatarId(asker, 'avatarDetailsResponse', [avId, 1, b'', b'', [], 0, 0, 0, 0])

        def answer(dclass, fields):
            try:
                if dclass != self.air.dclassesByName['DistributedToonUD'] or not fields:
                    return refuse()

                def get(name, default):
                    value = fields.get(name)
                    return value[0] if value else default
                experience, inventory = get('setExperience', None), get('setInventory', None)
                if experience is None or inventory is None:
                    return refuse()
                self.sendUpdateToAvatarId(asker, 'avatarDetailsResponse', [avId, 0, experience, inventory,
                 list(get('setTrackAccess', [0, 0, 0, 0, 1, 1, 0])), get('setMaxHp', 15), get('setHp', 15),
                 get('setDefaultShard', 0), get('setLastHood', 0)])
            except Exception:
                self.notify.warning('could not answer a details request for toon %s: %s' % (avId, traceback.format_exc()))
                refuse()
        try:
            self.air.dbInterface.queryObject(self.air.dbId, avId, answer)
        except Exception:
            self.notify.warning('could not ask the database for toon %s: %s' % (avId, traceback.format_exc()))
            refuse()

    # ---- a toon's own doodle, for the call-a-doodle button in battle (the client cannot ask the database for a pet itself)
    def requestPetDetails(self, petId):
        asker = self.air.getAvatarIdFromSender()
        if not asker or not petId:
            return
        now = time.time()
        if now - self.detailsAsked.get(('pet', asker), 0.0) < self.DETAILS_COOLDOWN:
            return
        self.detailsAsked[('pet', asker)] = now

        def refuse():
            self.sendUpdateToAvatarId(asker, 'petDetailsResponse', [petId, 1, '', []])

        def answer(dclass, fields):
            try:
                if not fields or 'setPetName' not in fields:
                    return refuse()

                def get(name, default):
                    value = fields.get(name)
                    return value[0] if value else default
                if get('setOwnerId', 0) != asker:
                    return refuse()               # only the owner may ask
                look = [get('setHead', -1), get('setEars', -1), get('setNose', -1), get('setTail', -1), get('setBodyTexture', 0),
                        get('setColor', 0), get('setColorScale', 0), get('setEyeColor', 0), get('setGender', 0)]
                self.sendUpdateToAvatarId(asker, 'petDetailsResponse', [petId, 0, get('setPetName', 'Doodle'), look])
            except Exception:
                self.notify.warning('could not answer a doodle request for %s: %s' % (petId, traceback.format_exc()))
                refuse()
        try:
            self.air.dbInterface.queryObject(self.air.dbId, petId, answer)
        except Exception:
            self.notify.warning('could not ask the database for doodle %s: %s' % (petId, traceback.format_exc()))
            refuse()

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
