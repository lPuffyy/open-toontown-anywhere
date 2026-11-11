"""Gifts between districts.

A toon buys a gift for a friend from the phone in their own district. When the friend is playing in ANOTHER district, writing the
gift into the database does not work: the friend's own district keeps the toon in memory and would overwrite it the next time it
saves. So the buyer's district asks every district (this object is a global one, every district listens on its channel) and the one
the friend is in puts the gift on their order and answers. If nobody answers in a few seconds, the friend is not playing and the
buyer's district writes the gift into the database instead (DistributedPhoneAI.__giftToOffline)."""
import time
import traceback

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalAI import DistributedObjectGlobalAI
from toontown.catalog import CatalogItem, CatalogItemList
from toontown.toonbase import ToontownGlobals

STORE = CatalogItem.Customization | CatalogItem.DeliveryDate
ANSWER_WAIT = 4.0


class DistributedDeliveryManagerAI(DistributedObjectGlobalAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedDeliveryManagerAI')

    def __init__(self, air):
        DistributedObjectGlobalAI.__init__(self, air)
        self.nextContext = 1
        self.waiting = {}            # context -> callback(result code or None for "nobody answered")

    def askToGift(self, targetId, item, senderId, price, callback):
        """Ask the other districts to put `item` on the gift order of `targetId`. callback(retcode) is called once: with a
        ToontownGlobals.P_* code when a district answered, or with None when none did."""
        context = self.nextContext
        self.nextContext += 1
        self.waiting[context] = callback
        blob = CatalogItemList.CatalogItemList([item], store=STORE).getBlob(STORE)
        self.sendUpdate('addGift', [targetId, blob, senderId, price, context])
        taskMgr.doMethodLater(ANSWER_WAIT, self.__noAnswer, 'gift-wait-%d' % context, extraArgs=[context])

    def __noAnswer(self, context):
        self.__finish(context, None)

    def __finish(self, context, code):
        callback = self.waiting.pop(context, None)
        taskMgr.remove('gift-wait-%d' % context)
        if callback is not None:
            try:
                callback(code)
            except Exception:
                self.notify.warning('gift answer failed: %s' % traceback.format_exc())

    # ---- the district the friend is in: another district asks (addGift), this one answers
    def addGift(self, targetId, blob, senderId, price, context):
        target = self.air.doId2do.get(targetId)
        if target is None or not hasattr(target, 'onGiftOrder'):
            return                                   # the friend is not in this district: another one answers
        try:
            items = CatalogItemList.CatalogItemList(blob, store=STORE)
            if len(items) != 1:
                raise ValueError('expected one item')
            item = items[0]
        except Exception:
            self.notify.warning('bad gift from district: %s' % traceback.format_exc())
            return self.__answer(context, targetId, ToontownGlobals.P_NotInCatalog)
        if len(target.mailboxContents) + len(target.onGiftOrder) >= ToontownGlobals.MaxMailboxContents:
            return self.__answer(context, targetId, ToontownGlobals.P_MailboxFull)
        if item in target.onGiftOrder or item in target.mailboxContents:
            return self.__answer(context, targetId, ToontownGlobals.P_ItemOnGiftOrder)
        target.onGiftOrder.append(item)
        target.sendUpdate('setGiftSchedule', [target.onGiftOrder.getBlob(STORE)])
        self.air.writeServerEvent('giftDelivered', senderId, '%d to %d across districts, price %d' % (context, targetId, price))
        self.__answer(context, targetId, ToontownGlobals.P_ItemAvailable)

    def __answer(self, context, targetId, retcode):
        self.sendUpdate('receiveAcceptPurchaseGift' if retcode == ToontownGlobals.P_ItemAvailable else 'receiveRejectPurchaseGift',
                        [context, targetId, retcode] if retcode == ToontownGlobals.P_ItemAvailable else [context, targetId, retcode, 0])

    # ---- the buyer's district: the answer comes back
    def receiveAcceptPurchaseGift(self, context, targetId, retcode):
        self.__finish(context, ToontownGlobals.P_ItemAvailable)

    def receiveRejectPurchaseGift(self, context, targetId, retcode, extra):
        self.__finish(context, retcode)
