import time
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.estate import HouseGlobals

NUM_SLOTS = 6


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

    def delete(self):
        DistributedObjectAI.delete(self)
