import os
import time
import traceback
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.catalog import CatalogItem
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.estate import PhoneGlobals
from toontown.toonbase import ToontownGlobals


MAX_ON_ORDER = 20
TEST_DELIVERY_MINUTES = 1     # test mode: every order arrives within a minute (set OT_CATALOG_TEST_DELIVERY=1, or catalog-test-delivery 1 in a prc)


def deliveryMinutes(item):
    """How long an order takes: the item's own time (an hour for clothes, four for windows, a day for furniture), or a minute in test mode."""
    minutes = item.getDeliveryTime()
    if os.environ.get('OT_CATALOG_TEST_DELIVERY') == '1' or simbase.config.GetBool('catalog-test-delivery', 0):
        minutes = min(minutes, TEST_DELIVERY_MINUTES)
    return minutes


class DistributedPhoneAI(DistributedFurnitureItemAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPhoneAI')

    def __init__(self, air, furnitureMgr, catalogItem):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, catalogItem)
        self.busyAvId = 0
        self.scale = (1.0, 1.0, 1.0)

    def getInitialScale(self):
        return self.scale

    def setNewScale(self, sx, sy, sz):
        self.scale = (sx, sy, sz)

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId, globalClockDelta.getRealNetworkTime(bits=16)])

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busyAvId:
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return
        self.busyAvId = avId
        # the catalog checks purchases against this (how many items are already in the house and attic)
        numHouseItems = 0
        av = self.air.doId2do.get(avId)
        house = self.air.doId2do.get(av.houseId) if av is not None and av.houseId else None
        if house is not None:
            numHouseItems = len(house.atticItems) + len(house.atticWallpaper) + len(house.atticWindows) + len(house.interiorItems)
        self.sendUpdateToAvatarId(avId, 'setLimits', [numHouseItems])
        if av is not None and av.catalogNotify == ToontownGlobals.NewItems:
            av.b_setCatalogNotify(ToontownGlobals.OldItems, av.mailboxNotify)         # looked at it: no more "new catalog" at each login
        self.d_setMovie(PhoneGlobals.PHONE_MOVIE_PICKUP, avId)

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.busyAvId:
            return
        self.busyAvId = 0
        self.d_setMovie(PhoneGlobals.PHONE_MOVIE_HANGUP, avId)
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
        self.d_setMovie(PhoneGlobals.PHONE_MOVIE_CLEAR, 0)

    def __purchase(self, av, item):
        """Checks the order the way the real server did, takes the money and queues the delivery. Returns a P_ code."""
        found, catalogType = None, CatalogItem.CatalogTypeWeekly
        for lst, kind in ((av.monthlyCatalog, CatalogItem.CatalogTypeMonthly), (av.weeklyCatalog, CatalogItem.CatalogTypeWeekly),
                          (av.backCatalog, CatalogItem.CatalogTypeBackorder)):
            if item in lst:
                found, catalogType = lst[lst.index(item)], kind
                break
        if found is None:
            return ToontownGlobals.P_NotInCatalog
        if item in av.onOrder:
            return ToontownGlobals.P_ItemOnOrder
        if item in av.mailboxContents:
            return ToontownGlobals.P_ItemInMailbox
        if found.reachedPurchaseLimit(av):
            return ToontownGlobals.P_ReachedPurchaseLimit
        if len(av.onOrder) >= MAX_ON_ORDER:
            return ToontownGlobals.P_OnOrderListFull
        if len(av.mailboxContents) + len(av.onOrder) >= ToontownGlobals.MaxMailboxContents:
            return ToontownGlobals.P_MailboxFull
        price = found.getPrice(catalogType)
        if av.getTotalMoney() < price:
            return ToontownGlobals.P_NotEnoughMoney
        av.takeMoney(price)
        item.deliveryDate = int(time.time() / 60) + deliveryMinutes(found)
        item.giftTag = None
        av.onOrder.append(item)
        av.d_setDeliverySchedule(av.onOrder)
        self.notify.info('%s bought %s for %s, arriving at minute %s' % (av.doId, item, price, item.deliveryDate))
        return ToontownGlobals.P_ItemAvailable

    def requestPurchaseMessage(self, context, blob, optional):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.busyAvId:
            retcode = ToontownGlobals.P_NotShopping
        else:
            try:
                retcode = self.__purchase(av, CatalogItem.getItem(blob, CatalogItem.Customization))
            except Exception:
                self.notify.warning('purchase failed: %s' % traceback.format_exc())
                retcode = ToontownGlobals.P_NotInCatalog
        self.sendUpdateToAvatarId(avId, 'requestPurchaseResponse', [context, retcode])

    def __giftCheck(self, av, item, targetId):
        """Returns (code, catalog item, price); code is P_ItemAvailable when the gift may go ahead."""
        found, catalogType = None, CatalogItem.CatalogTypeWeekly
        for lst, kind in ((av.monthlyCatalog, CatalogItem.CatalogTypeMonthly), (av.weeklyCatalog, CatalogItem.CatalogTypeWeekly),
                          (av.backCatalog, CatalogItem.CatalogTypeBackorder)):
            if item in lst:
                found, catalogType = lst[lst.index(item)], kind
                break
        if found is None:
            return ToontownGlobals.P_NotInCatalog, None, 0
        if not found.isGift():
            return ToontownGlobals.P_NotAGift, None, 0
        friends = [f[0] if isinstance(f, (tuple, list)) else f for f in av.getFriendsList()]
        if targetId == av.doId or targetId not in friends:
            return ToontownGlobals.P_NotInCatalog, None, 0
        price = found.getPrice(catalogType)
        if av.getTotalMoney() < price:
            return ToontownGlobals.P_NotEnoughMoney, None, 0
        return ToontownGlobals.P_ItemAvailable, found, price

    def requestGiftPurchaseMessage(self, context, targetId, blob, optional):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)

        def respond(retcode):
            self.sendUpdateToAvatarId(avId, 'requestGiftPurchaseResponse', [context, retcode])

        if av is None or avId != self.busyAvId:
            return respond(ToontownGlobals.P_NotShopping)
        try:
            item = CatalogItem.getItem(blob, CatalogItem.Customization)
            retcode, found, price = self.__giftCheck(av, item, targetId)
            if retcode != ToontownGlobals.P_ItemAvailable:
                return respond(retcode)
            item.deliveryDate = int(time.time() / 60) + deliveryMinutes(found)
            item.giftTag = avId
            item.giftCode = 0
            target = self.air.doId2do.get(targetId)
            if target is not None:
                if len(target.mailboxContents) + len(target.onGiftOrder) >= ToontownGlobals.MaxMailboxContents:
                    return respond(ToontownGlobals.P_MailboxFull)
                if item in target.onGiftOrder or item in target.mailboxContents:
                    return respond(ToontownGlobals.P_ItemOnGiftOrder)
                av.takeMoney(price)
                target.onGiftOrder.append(item)
                target.sendUpdate('setGiftSchedule', [target.onGiftOrder.getBlob(CatalogItem.Customization | CatalogItem.DeliveryDate)])
                return respond(ToontownGlobals.P_ItemAvailable)
            self.__giftToOffline(av, targetId, item, price, respond)
        except Exception:
            self.notify.warning('gift purchase failed: %s' % traceback.format_exc())
            respond(ToontownGlobals.P_NotInCatalog)

    def __giftToOffline(self, av, targetId, item, price, respond):
        """The friend is not playing: add the gift to their saved gift list in the database."""
        from toontown.catalog import CatalogItemList
        store = CatalogItem.Customization | CatalogItem.DeliveryDate

        def got(dclass, fields):
            try:
                if fields is None:
                    return respond(ToontownGlobals.P_NotInCatalog)
                old = fields.get('setGiftSchedule', (b'',))[0]
                gifts = CatalogItemList.CatalogItemList(old, store=store)
                if len(gifts) >= ToontownGlobals.MaxMailboxContents or item in gifts:
                    return respond(ToontownGlobals.P_MailboxFull)
                gifts.append(item)
                if av.getTotalMoney() < price:
                    return respond(ToontownGlobals.P_NotEnoughMoney)
                av.takeMoney(price)
                self.air.dbInterface.updateObject(self.air.dbId, targetId, dclass, {'setGiftSchedule': (gifts.getBlob(store),)})
                respond(ToontownGlobals.P_ItemAvailable)
            except Exception:
                self.notify.warning('offline gift failed: %s' % traceback.format_exc())
                respond(ToontownGlobals.P_NotInCatalog)

        self.air.dbInterface.queryObject(self.air.dbId, targetId, got, fieldNames=('setGiftSchedule',))
