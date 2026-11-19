# Parts of this file (the busy/free handling, the award and mail cases of avatarEnter, award indexing) are adapted from
# Toontown Infinite's DistributedMailboxAI, https://github.com/TT-Infinite-Archive/source, GNU AGPL-3.0 with additional terms:
# see NOTICE.md and LICENSE-AGPL-3.0. Copyright (C) 2016-2026 the Toontown Infinite contributors.
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
        self.busy = 0          # the avatar at the mailbox right now (one at a time)
        self.av = None

    def delete(self):
        self.ignoreAll()
        self.house = None
        DistributedObjectAI.delete(self)

    def generate(self):
        DistributedObjectAI.generate(self)
        owner = self.air.doId2do.get(self.house.ownerId)
        if owner is not None:
            self.fullIndicator = 1 if (len(owner.mailboxContents) or len(owner.awardMailboxContents) or owner.numMailItems or owner.getNumInvitesToShowInMailbox()) else 0

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

    def freeAvatar(self, avId):
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busy:
            # two toons asked at once: the first is served, the second is freed
            self.freeAvatar(avId)
            return
        av = self.air.doId2do.get(avId)
        if av is None:
            self.air.writeServerEvent('suspicious', avId, 'DistributedMailboxAI.avatarEnter unknown')
            return
        self.busy = avId
        self.av = av
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__handleUnexpectedExit, extraArgs=[avId])
        self.acceptOnce('bootAvFromEstate-' + str(avId), self.__handleBootMessage, extraArgs=[avId])
        if self.house.ownerId != avId:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_NOT_OWNER, avId])
            self.sendClearMovie()
        elif len(av.mailboxContents) != 0:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_READY, avId])
            if av.mailboxNotify == ToontownGlobals.NewItems:        # looked at them: no more "new mail" flag
                av.b_setCatalogNotify(av.catalogNotify, ToontownGlobals.OldItems)
        elif len(av.awardMailboxContents) != 0:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_READY, avId])
            if getattr(av, 'awardNotify', None) == ToontownGlobals.NewItems:
                av.b_setAwardNotify(ToontownGlobals.OldItems)
        elif av.numMailItems > 0 or av.getNumInvitesToShowInMailbox() > 0:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_READY, avId])
        elif len(av.onOrder) != 0:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_WAITING, avId])      # "your order is on its way"
            self.sendClearMovie()
        else:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_EMPTY, avId])
            self.sendClearMovie()

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busy == avId:
            self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_EXIT, avId])
            self.ignoreAll()
            self.busy = 0
            self.av = None
        self.freeAvatar(avId)

    def __handleUnexpectedExit(self, avId):
        self.notify.warning('avatar %s left the mailbox unexpectedly' % avId)
        self.sendClearMovie()

    def __handleBootMessage(self, avId):
        self.notify.warning('avatar %s was booted from the mailbox' % avId)
        self.sendClearMovie()

    def sendClearMovie(self):
        self.ignoreAll()
        self.busy = 0
        self.av = None
        self.sendUpdate('setMovie', [MailboxGlobals.MAILBOX_MOVIE_CLEAR, 0])

    def __find(self, av, item, index):
        """Awards fill the first slots, then the mailbox proper. Returns (stored item, is it an award), or (None, False)."""
        awards = av.awardMailboxContents
        if 0 <= index < len(awards):
            stored, isAward = awards[index], True
        elif 0 <= index - len(awards) < len(av.mailboxContents):
            stored, isAward = av.mailboxContents[index - len(awards)], False
        else:
            return None, False
        return (stored, isAward) if stored == item else (None, False)

    def __take(self, context, blob, index, accept, optional):
        """Shared by accept and discard: the item at `index` must be the one the client sent, then it leaves the mailbox."""
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.house.ownerId or self.busy != avId:
            return ToontownGlobals.P_NotAtMailbox
        item = CatalogItem.getItem(blob, CatalogItem.Customization)
        stored, isAward = self.__find(av, item, index)
        if stored is None:
            self.air.writeServerEvent('suspicious', avId, 'DistributedMailboxAI invalid index %s' % index)
            return ToontownGlobals.P_InvalidIndex
        retcode = ToontownGlobals.P_ItemAvailable
        if accept:
            retcode = stored.recordPurchase(av, optional)
            if retcode < 0:
                return retcode
        if isAward:
            contents = av.awardMailboxContents[:]
            del contents[index]
            av.b_setAwardMailboxContents(contents)
        else:
            contents = av.mailboxContents[:]
            del contents[index - len(av.awardMailboxContents)]
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
