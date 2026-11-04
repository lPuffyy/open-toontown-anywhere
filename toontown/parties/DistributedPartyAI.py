"""A party going on (ported from the original game): its grounds, clock, decorations, guests and activities."""
import datetime
import traceback
import types
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.parties import PartyGlobals, PartyUtils
from toontown.parties.PartyStoreAI import partyTuple

A = PartyGlobals.ActivityIds


def activityClass(activityId):
    """The server object for an activity, or None for activities that have none (the clock) or aren't made yet."""
    from toontown.parties import PartyActivitiesAI as P
    return P.ACTIVITY_CLASSES.get(activityId)


class DistributedPartyAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyAI')

    def __init__(self, air, hostId, zoneId, partyId, partyInfo, endTime):
        DistributedObjectAI.__init__(self, air)
        self.hostId = hostId
        self.partyZoneId = zoneId
        self.partyId = partyId
        self.info = partyInfo
        # (the activities, ported from the original game, read the party's info as attributes)
        self.partyInfo = types.SimpleNamespace(partyId=partyId, hostId=hostId, isPrivate=partyInfo['isPrivate'],
                                               inviteTheme=partyInfo['inviteTheme'])
        self.endTime = endTime
        self.inviteeIds = list(partyInfo['invitees'])
        self.avIdsAtParty = []
        self.startedTime = datetime.datetime.now()
        tm = getattr(air, 'toontownTimeManager', None)
        if tm is not None:
            self.startedTime = tm.getCurServerDateTime().replace(tzinfo=None)
        self.partyClockInfo = (0, 0, 0)
        for a in partyInfo['activities']:
            if a[0] == A.PartyClock:      # (the clock is drawn by the clients; it has no server object)
                self.partyClockInfo = (a[1], a[2], a[3])
        self.activityObjects = []

    def generate(self):
        DistributedObjectAI.generate(self)
        cannons = None
        for a in self.info['activities']:
            activityId, gx, gy, gh = a
            cls = activityClass(activityId)
            if cls is None:
                continue
            x = PartyUtils.convertDistanceFromPartyGrid(gx, 0)
            y = PartyUtils.convertDistanceFromPartyGrid(gy, 1)
            h = PartyUtils.convertDegreesFromPartyGrid(gh)
            try:
                if activityId == A.PartyCannon and cannons is not None:
                    cannons.spawnCannonAt(x, y, h)        # (every cannon on the grounds belongs to one cannon activity)
                    continue
                act = cls(self.air, self.doId, x, y, h)
                act.generateWithRequired(self.zoneId)    # (the cannon activity places its first cannon itself)
                self.activityObjects.append(act)
                if activityId == A.PartyCannon:
                    cannons = act
            except Exception:
                self.notify.warning('could not make activity %s: %s' % (activityId, traceback.format_exc()))

    def delete(self):
        for act in self.activityObjects:
            if not act.isDeleted():
                act.requestDelete()
        self.activityObjects = []
        DistributedObjectAI.delete(self)

    # required fields
    def getPartyClockInfo(self):
        return self.partyClockInfo

    def getInviteeIds(self):
        return self.inviteeIds

    def getPartyState(self):
        return False              # (True means the party is ending)

    def getPartyInfoTuple(self):
        info = dict(self.info)
        info['status'] = PartyGlobals.PartyStatus.Started
        return partyTuple(self.partyId, info)

    def getAvIdsAtParty(self):
        return self.avIdsAtParty

    def getPartyStartedTime(self):
        return self.startedTime.strftime('%Y-%m-%d %H:%M:%S')

    def getHostName(self):
        return self.info.get('hostName', '')

    def isInActivity(self, avId):
        return any(act.isInActivity(avId) for act in self.activityObjects if hasattr(act, 'isInActivity'))

    def b_setPartyState(self, ending):
        self.sendUpdate('setPartyState', [ending])

    # guests
    def avIdEnteredParty(self, avId):
        senderId = self.air.getAvatarIdFromSender()
        if senderId != avId or avId in self.avIdsAtParty:
            return
        self.avIdsAtParty.append(avId)
        self.sendUpdate('setAvIdsAtParty', [self.avIdsAtParty])
        self.air.partyManager.guestArrived(self, avId)

    def avIdLeft(self, avId):
        if avId in self.avIdsAtParty:
            self.avIdsAtParty.remove(avId)
            if not self.isDeleted():
                self.sendUpdate('setAvIdsAtParty', [self.avIdsAtParty])
        for act in self.activityObjects:
            try:
                act.toonLeftParty(avId)
            except Exception:
                pass
