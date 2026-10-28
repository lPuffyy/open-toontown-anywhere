import time
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.catalog import CatalogGenerator, CatalogItem
from toontown.toonbase import ToontownGlobals

WEEK_MINUTES = 7 * 24 * 60
WATCH_PERIOD = 20.0


class CatalogManagerAI(DistributedObjectAI):
    """Gives each toon their catalog. A toon starts on week 1 the first time we see them with an empty catalog,
    then moves on one week every real week."""
    notify = DirectNotifyGlobal.directNotify.newCategory('CatalogManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.generator = CatalogGenerator.CatalogGenerator()

    def generate(self):
        DistributedObjectAI.generate(self)
        taskMgr.doMethodLater(WATCH_PERIOD, self.__watch, 'catalogManagerWatch')

    def __watch(self, task):
        now = time.time() / 60
        for av in list(self.air.doId2do.values()):
            if av.__class__.__name__ != 'DistributedToonAI' or not hasattr(av, 'weeklyCatalog'):
                continue
            self.__deliverOrders(av, now)
            self.__topUpPetTricks(av)
            week, nextTime = av.getCatalogSchedule()
            empty = len(av.weeklyCatalog) == 0 and len(av.monthlyCatalog) == 0
            if week == 0 or empty or (nextTime and now >= nextTime):
                try:
                    self.deliverCatalogFor(av)
                except Exception:
                    import traceback
                    self.notify.warning('could not deliver a catalog to %s: %s' % (av.doId, traceback.format_exc()))
        return task.again

    def __topUpPetTricks(self, av):
        """A toon with a doodle can always find a trick to buy: if no trick they lack is on offer in their catalogs, put one in the weekly."""
        if getattr(av, 'petTrickPhraseOffered', False) or not getattr(av, 'petId', 0) or len(av.weeklyCatalog) + len(av.monthlyCatalog) == 0:
            return
        av.petTrickPhraseOffered = True
        from toontown.catalog.CatalogPetTrickItem import CatalogPetTrickItem, getAllPetTricks
        from toontown.catalog.CatalogItemList import CatalogItemList
        for catalog in (av.monthlyCatalog, av.weeklyCatalog, av.backCatalog):
            for item in catalog:
                if isinstance(item, CatalogPetTrickItem) and item.trickId not in av.petTrickPhrases:
                    return
        lacking = [item for item in getAllPetTricks() if item.trickId not in av.petTrickPhrases]
        if not lacking:
            return
        weekly = CatalogItemList(list(av.weeklyCatalog))
        weekly.append(lacking[0])
        av.b_setCatalog(av.monthlyCatalog, weekly, av.backCatalog)
        av.b_setCatalogNotify(ToontownGlobals.NewItems, av.mailboxNotify)
        self.notify.info('offered a pet trick to %s' % av.doId)

    def __deliverOrders(self, av, now):
        """Moves orders whose time has come from the toon's on-order list into their mailbox."""
        if len(av.onOrder) == 0 and len(av.onGiftOrder) == 0:
            return
        try:
            cutoff = int(now + 0.5)
            delivered, remaining = av.onOrder.extractDeliveryItems(cutoff)
            gifts, giftsLeft = av.onGiftOrder.extractDeliveryItems(cutoff)
            if len(delivered) == 0 and len(gifts) == 0:
                return
            if len(delivered):
                av.onOrder = remaining
                av.d_setDeliverySchedule(remaining)
            if len(gifts):
                av.onGiftOrder = giftsLeft
                av.sendUpdate('setGiftSchedule', [giftsLeft.getBlob(CatalogItem.Customization | CatalogItem.DeliveryDate)])
                delivered = delivered + gifts
            av.b_setMailboxContents(av.mailboxContents + delivered)
            av.b_setCatalogNotify(av.catalogNotify, ToontownGlobals.NewItems)
            self.notify.info('delivered %d orders to %s' % (len(delivered), av.doId))
        except Exception:
            import traceback
            self.notify.warning('could not deliver orders to %s: %s' % (av.doId, traceback.format_exc()))

    def isItemReleased(self, item):
        return True

    def startCatalog(self):
        av = self.air.doId2do.get(self.air.getAvatarIdFromSender())
        if av is not None:
            self.deliverCatalogFor(av)

    def deliverCatalogFor(self, av):
        now = int(time.time() / 60)
        week, nextTime = av.getCatalogSchedule()
        previousWeek = week
        if week == 0:
            week = 1
        elif nextTime and now >= nextTime:
            week += max(1, (now - nextTime) // WEEK_MINUTES + 1)
        monthly = self.generator.generateMonthlyCatalog(av, now)
        weekly = self.generator.generateWeeklyCatalog(av, week, monthly)
        back = self.generator.generateBackCatalog(av, week, previousWeek, weekly)
        av.b_setCatalog(monthly, weekly, back)
        av.b_setCatalogSchedule(week, now + WEEK_MINUTES)
        av.b_setCatalogNotify(ToontownGlobals.NewItems, av.mailboxNotify)
        self.notify.info('delivered catalog week %s to %s (%d monthly, %d weekly items)' % (week, av.doId, len(monthly), len(weekly)))
