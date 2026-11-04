import traceback
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.catalog import CatalogItem
from toontown.estate import MailboxGlobals
from toontown.toonbase import ToontownGlobals


class DistributedMailboxAI(DistributedObjectAI):
    """The mailbox in front of a house: holds what the owner ordered from the catalog until they accept or discard it."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedMailboxAI')

    def __init__(self, air, house):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.fullIndicator = 0

    def generate(self):
        DistributedObjectAI.generate(self)
        owner = self.air.doId2do.get(self.house.ownerId)
        if owner is not None:
            self.fullIndicator = 1 if len(owner.mailboxContents) else 0

    def getHouseId(self):
        return self.house.doId

    def getHousePos(self):
        return self.house.housePos

    def getName(self):
        return self.house.name

    def getFullIndicator(self):
        return self.fullIndicator

    def setFullIndicator(self, full):
        self.fullIndicator = full

    def d_setFullIndicator(self, full):
        self.sendUpdate('setFullIndicator', [full])

    def b_setFullIndicator(self, full):
        self.setFullIndicator(full)
        self.d_setFullIndicator(full)

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if avId != self.house.ownerId or av is None:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_NOT_OWNER, avId])
        elif len(av.mailboxContents) == 0:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_EMPTY, avId])
        else:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_READY, avId])

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_EXIT, avId])
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])

    def __take(self, context, blob, index, accept, optional):
        """Shared by accept and discard: the item at `index` must be the one the client sent, then it leaves the mailbox."""
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.house.ownerId:
            return ToontownGlobals.P_NotAtMailbox
        item = CatalogItem.getItem(blob, CatalogItem.Customization)
        if index < 0 or index >= len(av.mailboxContents):
            return ToontownGlobals.P_InvalidIndex
        stored = av.mailboxContents[index]
        if stored != item:
            return ToontownGlobals.P_InvalidIndex
        retcode = ToontownGlobals.P_ItemAvailable
        if accept:
            retcode = stored.recordPurchase(av, optional)
            if retcode < 0:
                return retcode
        contents = av.mailboxContents[:]
        del contents[index]
        av.b_setMailboxContents(contents)
        return retcode

    def acceptItemMessage(self, context, blob, index, optional):
        try:
            retcode = self.__take(context, blob, index, True, optional)
        except Exception:
            self.notify.warning('accepting a mailbox item failed: %s' % traceback.format_exc())
            retcode = ToontownGlobals.P_InvalidIndex
        self.sendUpdateToAvatarId(self.air.getAvatarIdFromSender(), 'acceptItemResponse', [context, retcode])

    def discardItemMessage(self, context, blob, index, optional):
        try:
            retcode = self.__take(context, blob, index, False, optional)
        except Exception:
            self.notify.warning('discarding a mailbox item failed: %s' % traceback.format_exc())
            retcode = ToontownGlobals.P_InvalidIndex
        self.sendUpdateToAvatarId(self.air.getAvatarIdFromSender(), 'discardItemResponse', [context, retcode])

    # party invitations (the party manager keeps them; see DistributedPartyManagerAI)
    def __answerInvite(self, context, inviteKey, status):
        from toontown.parties import PartyGlobals
        avId = self.air.getAvatarIdFromSender()
        toon = self.air.doId2do.get(avId)
        mine = toon is not None and any(i.inviteKey == inviteKey for i in getattr(toon, 'invites', []))
        if not mine:
            retcode = ToontownGlobals.P_InvalidIndex
        elif self.air.partyManager.setInviteStatus(avId, inviteKey, status):
            retcode = ToontownGlobals.P_ItemAvailable
        else:
            retcode = ToontownGlobals.P_InvalidIndex
        self.sendUpdateToAvatarId(avId, 'acceptItemResponse', [context, retcode])

    def acceptInviteMessage(self, context, inviteKey):
        from toontown.parties import PartyGlobals
        self.__answerInvite(context, inviteKey, PartyGlobals.InviteStatus.Accepted)

    def rejectInviteMessage(self, context, inviteKey):
        from toontown.parties import PartyGlobals
        self.__answerInvite(context, inviteKey, PartyGlobals.InviteStatus.Rejected)

    def markInviteReadButNotReplied(self, inviteKey):
        from toontown.parties import PartyGlobals
        avId = self.air.getAvatarIdFromSender()
        toon = self.air.doId2do.get(avId)
        for invite in getattr(toon, 'invites', []):
            if invite.inviteKey == inviteKey and invite.status == PartyGlobals.InviteStatus.NotRead:
                self.air.partyManager.setInviteStatus(avId, inviteKey, PartyGlobals.InviteStatus.ReadButNotReplied)
                break
