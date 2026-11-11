"""Parties (ported from the original game, where the AI party manager worked with an UberDOG and its database).

Planning: the host's party planner opens in a zone of its own (getPartyZone with planningParty), then sends addPartyRequest. The
party is checked, paid for, and saved in the shared party store (PartyStoreAI) with its invitees. Every toon's party fields (parties
hosted, invited to, invites, replies) are pushed from the store when the toon arrives and whenever the store changes.

Running: once its start time comes a party can start; the host goes to it from the Events page (getPartyZone), which builds the
party (DistributedPartyAI and its activities) in a new zone of this district. Friends find it with requestShardIdZoneIdForHostId,
everyone with public parties at a party gate. At its end time the guests are sent to the playground and the party is taken down."""
import datetime
import decimal
import time
import traceback
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.parties import PartyGlobals, PartyStoreAI
from toontown.parties.PartyStoreAI import TIME_FORMAT
from toontown.toonbase import ToontownGlobals

PartyStatus = PartyGlobals.PartyStatus
InviteStatus = PartyGlobals.InviteStatus
CHECK_EVERY = 15.0


class DistributedPartyManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.planningZones = {}          # hostId -> zone their party planner is using
        self.parties = {}                # hostId -> DistributedPartyAI running in this district
        self.zoneToHost = {}             # party zone -> hostId
        self.guestZone = {}              # avId -> party zone they are at
        self.pushed = {}                 # avId -> the party view last sent to that toon

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.accept('avatarEntered', self.__avatarEntered)
        taskMgr.doMethodLater(CHECK_EVERY, self.__tick, self.uniqueName('partyTick'))

    def delete(self):
        self.ignoreAll()
        taskMgr.remove(self.uniqueName('partyTick'))
        for hostId in list(self.parties):
            self.__endParty(hostId, status=None)
        DistributedObjectAI.delete(self)

    def canBuyParties(self):
        return True

    # ---- time ------------------------------------------------------------------------------------------------------------
    def now(self):
        tm = getattr(self.air, 'toontownTimeManager', None)
        if tm is not None:
            return tm.getCurServerDateTime().replace(tzinfo=None)
        return datetime.datetime.now()

    @staticmethod
    def parseTime(text):
        return datetime.datetime.strptime(text, TIME_FORMAT)

    # ---- keeping toons' party fields up to date --------------------------------------------------------------------------
    def __avatarEntered(self, av):
        self.pushed.pop(av.doId, None)
        self.pushToToon(av)
        if str(av.doId) in PartyStoreAI.read().get('owed', {}):
            owed = 0
            with PartyStoreAI.transaction() as data:
                owed = data.get('owed', {}).pop(str(av.doId), 0)
            if owed:
                av.addMoney(owed)          # a refund for a party that never started while they were away

    def pushToToon(self, av, data=None):
        try:
            data = data if data is not None else PartyStoreAI.read()
            hosted, invitedTo, invites, replies = PartyStoreAI.toonView(data, av.doId)
            view = (hosted, invitedTo, invites, replies)
            if self.pushed.get(av.doId) == view:
                return
            self.pushed[av.doId] = view
            av.setHostedParties(hosted)
            av.sendUpdate('setHostedParties', [hosted])
            av.setPartiesInvitedTo(invitedTo)
            av.sendUpdate('setPartiesInvitedTo', [invitedTo])
            av.setInvites(invites)
            av.sendUpdate('setInvites', [invites])
            av.updateInviteMailNotify()
            av.sendUpdate('setPartyReplies', [replies])
        except Exception:
            self.notify.warning('could not send party info to %s: %s' % (av.doId, traceback.format_exc()))

    def __pushAll(self):
        data = PartyStoreAI.read()
        for av in list(self.air.doId2do.values()):
            if av.__class__.__name__ == 'DistributedToonAI' and not av.isDeleted():
                self.pushToToon(av, data)

    def __tick(self, task):
        """Parties whose time has come can start; parties whose time is over and never started are refunded."""
        try:
            now = self.now()
            refunds = []
            with PartyStoreAI.transaction() as data:
                for pid, p in data['parties'].items():
                    if p['status'] == PartyStatus.Pending and now >= self.parseTime(p['start']):
                        p['status'] = PartyStatus.CanStart
                    if p['status'] in (PartyStatus.Pending, PartyStatus.CanStart) and now >= self.parseTime(p['end']):
                        p['status'] = PartyStatus.NeverStarted
                        if not p.get('refunded'):
                            p['refunded'] = True
                            refunds.append((p['hostId'], int(pid), p.get('cost', 0)))
                for hostId, run in list(data['running'].items()):
                    if int(hostId) in self.parties:
                        run['beat'] = time.time()          # (still going on here)
                    elif run.get('beat', 0) + 3 * CHECK_EVERY < time.time():
                        # a party whose district went away (restarted) without cleaning up: the host can start it again
                        del data['running'][hostId]
                runningIds = {run.get('partyId') for run in data['running'].values()}
                for pid, p in data['parties'].items():
                    if p['status'] == PartyStatus.Started and int(pid) not in runningIds:
                        # (no district has it going any more, e.g. it was restarted: the host can start it again)
                        p['status'] = PartyStatus.CanStart if now < self.parseTime(p['end']) else PartyStatus.Finished
                # parties long over are forgotten after a week
                old = [pid for pid, p in data['parties'].items()
                       if p['status'] in (PartyStatus.Cancelled, PartyStatus.Finished, PartyStatus.NeverStarted)
                       and now > self.parseTime(p['end']) + datetime.timedelta(days=7)]
                for pid in old:
                    del data['parties'][pid]
            for hostId, partyId, cost in refunds:
                self.__refund(hostId, partyId, cost, PartyStatus.NeverStarted)
            for hostId, party in list(self.parties.items()):
                if now >= party.endTime:
                    self.__endParty(hostId)
            self.__pushAll()
        except Exception:
            self.notify.warning('party check failed: %s' % traceback.format_exc())
        return task.again

    def __refund(self, hostId, partyId, cost, status):
        refund = int(cost * PartyGlobals.PartyRefundPercentage)
        host = self.air.doId2do.get(hostId)
        if host is not None and refund > 0:
            host.addMoney(refund)
            host.sendUpdate('setPartyStatus', [partyId, status])
        elif refund > 0:
            # (offline: kept and paid the next time they come on)
            with PartyStoreAI.transaction() as data:
                data.setdefault('owed', {})
                data['owed'][str(hostId)] = data['owed'].get(str(hostId), 0) + refund
        return refund

    # ---- planning ---------------------------------------------------------------------------------------------------------
    def getPartyZone(self, hostId, zoneId, planningParty):
        senderId = self.air.getAvatarIdFromSender()
        if planningParty:
            if hostId != senderId:
                return self.__noZone(senderId)
            zone = self.planningZones.get(senderId) or self.air.allocateZone()
            self.planningZones[senderId] = zone
            self.sendUpdateToAvatarId(senderId, 'receivePartyZone', [senderId, 0, zone])
            return
        if zoneId > 0 and zoneId in self.zoneToHost:
            hostId = self.zoneToHost[zoneId]
        party = self.parties.get(hostId)
        if party is None and hostId == senderId:
            party = self.__startParty(senderId)
        if party is None:
            return self.__noZone(senderId)
        if senderId != hostId and party.info['isPrivate'] and senderId not in party.inviteeIds:
            return self.__noZone(senderId)
        if senderId != hostId and len(party.avIdsAtParty) >= PartyGlobals.MaxToonsAtAParty and senderId not in party.avIdsAtParty:
            return self.__noZone(senderId)
        self.guestZone[senderId] = party.zoneId
        self.acceptOnce(self.air.getAvatarExitEvent(senderId), self.__guestGone, [senderId])
        self.sendUpdateToAvatarId(senderId, 'receivePartyZone', [hostId, party.partyId, party.zoneId])

    def __noZone(self, avId):
        self.sendUpdateToAvatarId(avId, 'receivePartyZone', [0, 0, 0])

    def freeZoneIdFromPlannedParty(self, hostId, zoneId):
        senderId = self.air.getAvatarIdFromSender()
        if self.planningZones.get(senderId) == zoneId:
            del self.planningZones[senderId]
            self.air.deallocateZone(zoneId)

    def addPartyRequest(self, hostId, startTime, endTime, isPrivate, inviteTheme, activities, decorations, inviteeIds):
        senderId = self.air.getAvatarIdFromSender()
        host = self.air.doId2do.get(senderId)
        if host is None or hostId != senderId:
            return
        error, cost = self.__validate(host, startTime, endTime, activities, decorations, inviteeIds, isPrivate, inviteTheme)
        if error == PartyGlobals.AddPartyErrorCode.AllOk:
            if not host.takeMoney(cost):
                error = PartyGlobals.AddPartyErrorCode.ValidationError
        if error == PartyGlobals.AddPartyErrorCode.AllOk:
            try:
                with PartyStoreAI.transaction() as data:
                    pid = str(data['nextPartyId'])
                    data['nextPartyId'] += 1
                    data['parties'][pid] = {'hostId': hostId, 'hostName': host.getName(), 'start': startTime, 'end': endTime,
                                            'isPrivate': int(isPrivate), 'inviteTheme': int(inviteTheme),
                                            'activities': [list(a) for a in activities], 'decors': [list(d) for d in decorations],
                                            'status': PartyStatus.Pending, 'invitees': list(inviteeIds), 'cost': cost}
                    for inviteeId in inviteeIds:
                        key = data['nextInviteKey']
                        data['nextInviteKey'] += 1
                        data['invites'].setdefault(str(inviteeId), []).append([key, int(pid), InviteStatus.NotRead])
                self.air.writeServerEvent('partyPlanned', hostId, '%s %s-%s cost %d' % (pid, startTime, endTime, cost))
            except Exception:
                self.notify.warning('could not save a party: %s' % traceback.format_exc())
                host.addMoney(cost)
                error = PartyGlobals.AddPartyErrorCode.DatabaseError
        self.sendUpdateToAvatarId(hostId, 'addPartyResponse', [hostId, error])
        if error == PartyGlobals.AddPartyErrorCode.AllOk:
            self.__pushAll()

    @staticmethod
    def __gridRange(center, size):
        """The grid squares an item of this size covers around its centre (rounding halves up, as the original game did)."""
        if size == 1:
            return [center]
        D = decimal.Decimal
        rounded = int(D(str(size / 2)).quantize(D('1.'), rounding=decimal.ROUND_HALF_UP))
        return list(range(int(center + size / 2), int(center - rounded), -1))

    def __holidayOn(self, holidayId):
        mgr = getattr(self.air, 'holidayManager', None)
        return bool(mgr is not None and mgr.isHolidayRunning(holidayId))

    def __validate(self, host, startTime, endTime, activities, decorations, inviteeIds, isPrivate=0, inviteTheme=0):
        """Checks a party the way the original game did: only one party at a time, sane dates, the invitation theme, every activity and
        decoration (known, released, allowed by the holiday, inside the editor's grid, not overlapping, not over its limit, no
        mutually exclusive pairs) and that the host can pay. Returns (error code, cost)."""
        Err = PartyGlobals.AddPartyErrorCode
        bad = lambda why: self.__reject(host, why)
        if not host.canPlanParty():
            return Err.TooManyHostedParties, 0
        try:
            start, end = self.parseTime(startTime), self.parseTime(endTime)
        except Exception:
            return bad('unreadable times')
        if not (PartyGlobals.MinPlannedYear <= start.year <= PartyGlobals.MaxPlannedYear and
                PartyGlobals.MinPlannedYear <= end.year <= PartyGlobals.MaxPlannedYear):
            return bad('year out of range')
        if end <= start or end < self.now() or (end - start) > datetime.timedelta(hours=24):
            return bad('bad length')
        if isPrivate not in (0, 1):
            return bad('bad isPrivate %r' % (isPrivate,))
        if inviteTheme not in [int(x) for x in PartyGlobals.InviteTheme]:
            return bad('bad theme %r' % (inviteTheme,))
        if inviteTheme == PartyGlobals.InviteTheme.Valentoons and not self.__holidayOn(ToontownGlobals.VALENTINES_DAY):
            return bad('Valentoons theme out of season')
        if inviteTheme == PartyGlobals.InviteTheme.VictoryParty and not self.__holidayOn(ToontownGlobals.VICTORY_PARTY_HOLIDAY):
            return bad('Victory Party theme out of season')

        cost = 0
        used = {}                               # grid square -> what covers it
        gridW, gridH = PartyGlobals.PartyEditorGridSize
        victory = self.__holidayOn(ToontownGlobals.VICTORY_PARTY_HOLIDAY)
        valentine = self.__holidayOn(ToontownGlobals.VALENTINES_DAY)
        counts, actIds = {}, set()
        for a in activities:
            aid = a[0]
            info = PartyGlobals.ActivityInformationDict.get(aid)
            if info is None:
                return bad('unknown activity %r' % (aid,))
            if aid in PartyGlobals.VictoryPartyActivityIds and not victory:
                return bad('Victory Party activity out of season')
            if aid in PartyGlobals.VictoryPartyReplacementActivityIds and victory:
                return bad('activity replaced during the Victory Party')
            if aid in PartyGlobals.UnreleasedActivityIds:
                return bad('activity not released')
            if not (0 <= a[1] < gridW and 0 <= a[2] < gridH and 0 <= a[3] <= 255):
                return bad('activity placed outside the editor')
            counts[aid] = counts.get(aid, 0) + 1
            actIds.add(aid)
            cost += info['cost']
            for gy in self.__gridRange(a[2], info['gridsize'][1]):
                for gx in self.__gridRange(a[1], info['gridsize'][0]):
                    if (gx, gy) in used:
                        return bad('activity overlaps at %s' % ((gx, gy),))
                    used[(gx, gy)] = 'activity-%d' % aid
        for aid, n in counts.items():
            if n > PartyGlobals.ActivityInformationDict[aid]['limitPerParty']:
                return bad('too many of activity %r' % (aid,))
        for pair in PartyGlobals.MutuallyExclusiveActivities:
            if len(set(pair) & actIds) > 1:
                return bad('mutually exclusive activities')

        dcounts = {}
        heart = ('HeartTarget', 'HeartBanner', 'FlyingHeart')
        for d in decorations:
            did = d[0]
            info = PartyGlobals.DecorationInformationDict.get(did)
            if info is None:
                return bad('unknown decoration %r' % (did,))
            if PartyGlobals.DecorationIds(did).name in heart and not valentine:
                return bad('Valentoons decoration out of season')
            if did in PartyGlobals.VictoryPartyDecorationIds and not victory:
                return bad('Victory Party decoration out of season')
            if did in PartyGlobals.VictoryPartyReplacementDecorationIds and victory:
                return bad('decoration replaced during the Victory Party')
            if did in PartyGlobals.UnreleasedDecorationIds:
                return bad('decoration not released')
            if not (0 <= d[1] < gridW and 0 <= d[2] < gridH and 0 <= d[3] <= 255):
                return bad('decoration placed outside the editor')
            dcounts[did] = dcounts.get(did, 0) + 1
            cost += info['cost']
            for gy in self.__gridRange(d[2], info['gridsize'][1]):
                for gx in self.__gridRange(d[1], info['gridsize'][0]):
                    if (gx, gy) in used:
                        return bad('decoration overlaps at %s' % ((gx, gy),))
                    used[(gx, gy)] = 'decor-%d' % did
        for did, n in dcounts.items():
            if n > PartyGlobals.DecorationInformationDict[did]['limitPerParty']:
                return bad('too many of decoration %r' % (did,))
        if len(used) >= PartyGlobals.AvailableGridSquares:
            return bad('no free grid square left')
        if len(inviteeIds) > 200 or cost > host.getTotalMoney():
            return bad('too many invitees or too expensive (%d)' % cost)
        return Err.AllOk, cost

    def __reject(self, host, why):
        self.notify.warning('party from %s refused: %s' % (host.doId, why))
        self.air.writeServerEvent('partyRefused', host.doId, why)
        return PartyGlobals.AddPartyErrorCode.ValidationError, 0

    def changePrivateRequest(self, partyId, newPrivateStatus):
        senderId = self.air.getAvatarIdFromSender()
        err = PartyGlobals.ChangePartyFieldErrorCode.ValidationError
        with PartyStoreAI.transaction() as data:
            p = data['parties'].get(str(partyId))
            if p is not None and p['hostId'] == senderId:
                if p['status'] == PartyStatus.Started:
                    err = PartyGlobals.ChangePartyFieldErrorCode.AlreadyStarted
                else:
                    p['isPrivate'] = int(newPrivateStatus)
                    err = PartyGlobals.ChangePartyFieldErrorCode.AllOk
        self.sendUpdateToAvatarId(senderId, 'changePrivateResponse', [partyId, newPrivateStatus, err])
        self.__pushAll()

    def changePartyStatusRequest(self, partyId, newPartyStatus):
        """The host cancels a party from the Events page: it is refunded (less a little)."""
        senderId = self.air.getAvatarIdFromSender()
        Err = PartyGlobals.ChangePartyFieldErrorCode
        err, cost = Err.ValidationError, 0
        with PartyStoreAI.transaction() as data:
            p = data['parties'].get(str(partyId))
            if p is not None and p['hostId'] == senderId and newPartyStatus == PartyStatus.Cancelled:
                if p['status'] == PartyStatus.Started:
                    err = Err.AlreadyStarted
                elif p.get('refunded'):
                    err = Err.AlreadyRefunded
                elif p['status'] in (PartyStatus.Pending, PartyStatus.CanStart):
                    p['status'] = PartyStatus.Cancelled
                    p['refunded'] = True
                    cost = p.get('cost', 0)
                    err = Err.AllOk
        refund = 0
        if err == Err.AllOk:
            refund = int(cost * PartyGlobals.PartyRefundPercentage)
            host = self.air.doId2do.get(senderId)
            if host is not None and refund:
                host.addMoney(refund)
        self.sendUpdateToAvatarId(senderId, 'changePartyStatusResponse', [partyId, newPartyStatus, err, refund])
        self.__pushAll()

    # ---- invitations (from the mailbox) ---------------------------------------------------------------------------------------
    def setInviteStatus(self, avId, inviteKey, status):
        found = False
        with PartyStoreAI.transaction() as data:
            for invite in data['invites'].get(str(avId), []):
                if invite[0] == inviteKey:
                    invite[2] = int(status)
                    found = True
        av = self.air.doId2do.get(avId)
        if found and av is not None:
            av.updateInvite(inviteKey, status)
            av.sendUpdate('updateInvite', [inviteKey, status])
        if found:
            self.__pushAll()
        return found

    # ---- running parties ----------------------------------------------------------------------------------------------------
    def __startParty(self, hostId):
        from toontown.parties.DistributedPartyAI import DistributedPartyAI
        host = self.air.doId2do.get(hostId)
        if host is None:
            return None
        started = None
        with PartyStoreAI.transaction() as data:
            if str(hostId) in data['running']:
                return None                            # (already going on in another district)
            for pid, p in data['parties'].items():
                if p['hostId'] == hostId and p['status'] == PartyStatus.CanStart:
                    p['status'] = PartyStatus.Started
                    started = (int(pid), dict(p))
                    break
            if started is None:
                return None
            zoneId = self.air.allocateZone()
            data['running'][str(hostId)] = {'partyId': started[0], 'shardId': self.air.districtId, 'zoneId': zoneId, 'beat': time.time(),
                                            'guests': 0, 'hostName': host.getName(), 'isPrivate': started[1]['isPrivate'],
                                            'activityIds': [a[0] for a in started[1]['activities']],
                                            'endTime': time.mktime(self.parseTime(started[1]['end']).timetuple())}
        partyId, info = started
        party = DistributedPartyAI(self.air, hostId, zoneId, partyId, info, self.parseTime(info['end']))
        party.generateWithRequired(zoneId)
        self.parties[hostId] = party
        self.zoneToHost[zoneId] = hostId
        self.air.writeServerEvent('partyStarted', hostId, '%s zone %s' % (partyId, zoneId))
        self.__announceStarted(partyId, info)
        return party

    def __announceStarted(self, partyId, info):
        for avId in info['invitees']:
            av = self.air.doId2do.get(avId)
            if av is not None:
                av.sendUpdate('announcePartyStarted', [partyId])
        host = self.air.doId2do.get(info['hostId'])
        if host is not None:
            host.sendUpdate('setPartyStatus', [partyId, PartyStatus.Started])

    def guestArrived(self, party, avId):
        self.guestZone[avId] = party.zoneId
        self.__updateGuestCount(party)

    def __updateGuestCount(self, party):
        try:
            with PartyStoreAI.transaction() as data:
                run = data['running'].get(str(party.hostId))
                if run is not None:
                    run['guests'] = len(party.avIdsAtParty)
        except Exception:
            pass

    def exitParty(self, zoneId):
        self.__guestGone(self.air.getAvatarIdFromSender())

    def __guestGone(self, avId):
        zoneId = self.guestZone.pop(avId, None)
        hostId = self.zoneToHost.get(zoneId)
        party = self.parties.get(hostId)
        if party is not None:
            party.avIdLeft(avId)
            self.__updateGuestCount(party)

    def removeGuest(self, ownerId, avId):
        if self.air.getAvatarIdFromSender() != ownerId or ownerId not in self.parties:
            return
        if self.guestZone.get(avId) == self.parties[ownerId].zoneId:
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 0])
            self.__guestGone(avId)

    def getPartyEndedEvent(self, hostId):
        return 'partyEnded-%d' % hostId

    def __endParty(self, hostId, status=PartyStatus.Finished):
        party = self.parties.pop(hostId, None)
        if party is None:
            return
        messenger.send(self.getPartyEndedEvent(hostId))
        party.b_setPartyState(True)
        for avId in list(party.avIdsAtParty):
            self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 0])
            self.guestZone.pop(avId, None)
        self.zoneToHost.pop(party.zoneId, None)
        zoneId = party.zoneId
        party.requestDelete()
        taskMgr.doMethodLater(30, lambda task: (self.air.deallocateZone(zoneId), task.done)[1], self.uniqueName('freeZone-%d' % zoneId))
        try:
            with PartyStoreAI.transaction() as data:
                data['running'].pop(str(hostId), None)
                p = data['parties'].get(str(party.partyId))
                if p is not None and status is not None:
                    p['status'] = status
        except Exception:
            self.notify.warning('could not mark party %s over' % party.partyId)

    def requestShardIdZoneIdForHostId(self, hostId):
        senderId = self.air.getAvatarIdFromSender()
        run = PartyStoreAI.read()['running'].get(str(hostId))
        if run is None:
            return self.sendUpdateToAvatarId(senderId, 'sendShardIdZoneIdToAvatar', [0, 0])
        self.sendUpdateToAvatarId(senderId, 'sendShardIdZoneIdToAvatar', [run['shardId'], run['zoneId']])

    def getAllPublicParties(self):
        """For the party gates: (district, zone, guests, host name, activities, minutes left) of every public party going on."""
        out = []
        now = time.time()
        for hostId, run in PartyStoreAI.read()['running'].items():
            if run.get('isPrivate'):
                continue
            minLeft = max(0, int((run.get('endTime', now) - now) / 60))
            out.append((run['shardId'], run['zoneId'], min(255, run.get('guests', 0)), run.get('hostName', ''),
                        list(run.get('activityIds', [])), min(65535, minLeft)))
        return out
