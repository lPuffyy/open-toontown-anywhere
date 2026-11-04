import json
import os
import time
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.estate import HouseGlobals
from toontown.toonbase import ToontownGlobals

NUM_SLOTS = 6
SAVE_DIR = 'estate_data'


class DistributedEstateAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedEstateAI')

    def __init__(self, air, ownerId):
        DistributedObjectAI.__init__(self, air)
        self.ownerId = ownerId
        self.houses = []
        self.estateType = 0
        self.dawnTime = int(time.time()) % HouseGlobals.DAY_NIGHT_PERIOD
        self.decorData = []
        self.lastEpochTimeStamp = 0
        self.rentalTimeStamp = 0
        self.rentalType = 0
        self.slotToonId = [0] * NUM_SLOTS
        self.slotItems = [[] for _ in range(NUM_SLOTS)]
        self.slotToonId[0] = ownerId
        self.clouds = 0
        self.idList = []
        self.treasureIds = []
        self.treasurePlanner = None
        self.flyingTreasurePlanner = None
        self.target = None
        self.gameTable = None
        self.cannonsOn = False
        # the required "slot" fields are numbered, so give each its own getter and setter
        for i in range(NUM_SLOTS):
            setattr(self, 'getSlot%dToonId' % i, lambda i=i: self.slotToonId[i])
            setattr(self, 'setSlot%dToonId' % i, lambda v, i=i: self.slotToonId.__setitem__(i, v))
            setattr(self, 'getSlot%dItems' % i, lambda i=i: self.slotItems[i])
            setattr(self, 'setSlot%dItems' % i, lambda v, i=i: self.slotItems.__setitem__(i, v))

    # required fields
    def getEstateType(self):
        return self.estateType

    def getDawnTime(self):
        return self.dawnTime

    def getDecorData(self):
        return self.decorData

    def setDecorData(self, data):
        self.decorData = data

    def getLastEpochTimeStamp(self):
        return self.lastEpochTimeStamp

    def setLastEpochTimeStamp(self, ts):
        self.lastEpochTimeStamp = ts

    def getRentalTimeStamp(self):
        return self.rentalTimeStamp

    def setRentalTimeStamp(self, ts):
        self.rentalTimeStamp = ts

    def getRentalType(self):
        return self.rentalType

    def setRentalType(self, t):
        self.rentalType = t

    def getClouds(self):
        return self.clouds

    # client messages
    def setClientReady(self):
        self.sendUpdate('setEstateReady', [])

    def setClosestHouse(self, index):
        pass

    def requestServerTime(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'setServerTime', [int(time.time()) % HouseGlobals.DAY_NIGHT_PERIOD])

    def completeFlowerSale(self, sell):
        """The owner has put their flower basket on the scale: pay for it (or keep it) and empty the basket."""
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.ownerId:
            return
        if sell and len(av.flowerBasket):
            av.addMoney(av.flowerBasket.getTotalValue())
            av.b_setFlowerBasket([], [])

    def placeStarterGarden(self, avId):
        av = self.air.doId2do.get(avId)
        if av is not None and not av.getGardenStarted():
            av.b_setGardenStarted(1)

    # rentals (bought from the catalog: cannons with a target and flying treasures, or a game table) -----------------
    def start(self):
        """Called once the houses exist: treasures on the ground, and any rental that was still running."""
        from toontown.safezone.ETreasurePlannerAI import ETreasurePlannerAI
        self.treasurePlanner = ETreasurePlannerAI(self.zoneId)
        self.treasurePlanner.start()
        saved = self.__loadRental()
        if saved and saved.get('until', 0) > time.time():
            self.rentalType, self.rentalTimeStamp = saved['type'], int(saved['until'])
            self.__startRental()

    def __rentalPath(self):
        return os.path.join(SAVE_DIR, '%d_rental.json' % self.ownerId)

    def __loadRental(self):
        try:
            with open(self.__rentalPath()) as f:
                return json.load(f)
        except Exception:
            return None

    def __saveRental(self):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            with open(self.__rentalPath(), 'w') as f:
                json.dump({'type': self.rentalType, 'until': self.rentalTimeStamp}, f)
        except Exception:
            self.notify.warning('could not save the rental of %s' % self.ownerId)

    @staticmethod
    def rentWhileAway(ownerId, rentalType, duration):
        """A rental bought while the owner's estate isn't loaded: save it, and it starts the next time the estate is built."""
        path = os.path.join(SAVE_DIR, '%d_rental.json' % ownerId)
        now = time.time()
        try:
            with open(path) as f:
                saved = json.load(f)
        except Exception:
            saved = {}
        left = max(0, saved.get('until', 0) - now) if saved.get('type') == rentalType else 0
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            with open(path, 'w') as f:
                json.dump({'type': rentalType, 'until': int(now + duration * 60 + left)}, f)
        except Exception:
            DistributedEstateAI.notify.warning('could not save the rental of %s' % ownerId)

    def rentItem(self, rentalType, duration):
        """A rental was bought (`duration` in minutes). Renting the same thing again adds to the time left."""
        now = time.time()
        left = max(0, self.rentalTimeStamp - now) if rentalType == self.rentalType else 0
        if rentalType != self.rentalType:
            self.__stopRental()
        self.rentalType = rentalType
        self.rentalTimeStamp = int(now + duration * 60 + left)
        self.__saveRental()
        self.notify.info('estate of %s: rental %s until %s' % (self.ownerId, rentalType, self.rentalTimeStamp))
        self.__startRental()

    def __startRental(self):
        taskMgr.remove(self.uniqueName('endRental'))
        taskMgr.doMethodLater(max(1, self.rentalTimeStamp - time.time()), self.__rentalOver, self.uniqueName('endRental'))
        if self.rentalType == ToontownGlobals.RentalCannon:
            self.__startCannons()
        elif self.rentalType == ToontownGlobals.RentalGameTable:
            self.__startGameTable()

    def __rentalOver(self, task=None):
        if self.rentalType == ToontownGlobals.RentalCannon and self.cannonsOn:
            self.sendUpdate('cannonsOver', [])
        elif self.rentalType == ToontownGlobals.RentalGameTable and self.gameTable is not None:
            self.sendUpdate('gameTableOver', [])
        self.__stopRental()
        self.rentalType, self.rentalTimeStamp = 0, 0
        self.__saveRental()
        if task is not None:
            return task.done

    def __stopRental(self):
        taskMgr.remove(self.uniqueName('endRental'))
        self.__endCannons()
        self.__endGameTable()

    def __startCannons(self):
        if self.cannonsOn:
            return
        from toontown.estate.DistributedTargetAI import DistributedTargetAI
        from toontown.safezone.EFlyingTreasurePlannerAI import EFlyingTreasurePlannerAI
        self.flyingTreasurePlanner = EFlyingTreasurePlannerAI(self, self.zoneId)
        self.flyingTreasurePlanner.start()
        self.updateFlyingTreasureList()
        self.target = DistributedTargetAI(self.air, -5.6, -24, 50)
        self.target.generateWithRequired(self.zoneId)
        self.target.start()
        for house in self.houses:
            house.setCannonEnabled(1, self.doId, self.target.doId)
        self.b_setClouds(1)
        self.cannonsOn = True

    def __endCannons(self):
        if not self.cannonsOn:
            return
        for house in self.houses:
            house.setCannonEnabled(0)
        if self.flyingTreasurePlanner is not None:
            self.flyingTreasurePlanner.stop()
            self.flyingTreasurePlanner.deleteAllTreasuresNow()
            self.flyingTreasurePlanner = None
            self.updateFlyingTreasureList()
        if self.target is not None:
            if not self.target.isDeleted():
                self.target.requestDelete()
            self.target = None
        self.b_setClouds(0)
        self.cannonsOn = False

    def updateFlyingTreasureList(self):
        """The clients need the flying treasures' ids to see whether a toon shot from a cannon hits one."""
        planner = self.flyingTreasurePlanner
        self.treasureIds = [t.doId for t in planner.treasures if t] if planner is not None else []
        if not self.isDeleted():
            self.sendUpdate('setTreasureIds', [self.treasureIds])

    def getTreasureIds(self):
        return self.treasureIds

    def __startGameTable(self):
        if self.gameTable is None:
            from toontown.safezone.DistributedPicnicTableAI import DistributedPicnicTableAI
            self.gameTable = DistributedPicnicTableAI(self.air, self.zoneId, 'gameTable', 55, -20, 8.8, 0, 0, 0)

    def __endGameTable(self):
        if self.gameTable is not None:
            if not self.gameTable.isDeleted():
                self.gameTable.requestDelete()
            self.gameTable = None

    def b_setClouds(self, clouds):
        self.clouds = clouds
        self.sendUpdate('setClouds', [clouds])

    def delete(self):
        taskMgr.remove(self.uniqueName('endRental'))
        self.__endCannons()
        self.__endGameTable()
        if self.treasurePlanner is not None:
            self.treasurePlanner.stop()
            self.treasurePlanner.deleteAllTreasuresNow()
            self.treasurePlanner = None
        DistributedObjectAI.delete(self)
