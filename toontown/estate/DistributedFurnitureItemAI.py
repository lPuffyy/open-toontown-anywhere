from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedSmoothNodeAI import DistributedSmoothNodeAI
from direct.distributed.ClockDelta import globalClockDelta
from toontown.estate import HouseGlobals
from toontown.toonbase import ToontownGlobals


class DistributedFurnitureItemAI(DistributedSmoothNodeAI):
    """One piece of furniture standing in a house interior."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureItemAI')

    def __init__(self, air, furnitureMgr, catalogItem):
        DistributedSmoothNodeAI.__init__(self, air)
        self.furnitureMgr = furnitureMgr
        self.catalogItem = catalogItem
        self.mode = HouseGlobals.FURNITURE_MODE_OFF
        self.modeAvId = 0

    def getItem(self):
        from toontown.catalog import CatalogItem
        return (self.furnitureMgr.doId, self.catalogItem.getBlob(store=CatalogItem.Customization))

    def getMode(self):
        return (self.mode, self.modeAvId)

    def placeInRoom(self):
        """Put the item at the position stored in its catalog entry."""
        self.b_setParent(ToontownGlobals.SPRender)
        pos = self.catalogItem.posHpr or (0, 0, 0, 0, 0, 0)
        self.setPosHpr(*pos)
        self.sendUpdate('setSmPosHpr', [pos[0], pos[1], pos[2], pos[3], pos[4], pos[5], globalClockDelta.getFrameNetworkTime()])

    def requestPosHpr(self, final, x, y, z, h, p, r, timestamp):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.furnitureMgr.director:
            return
        self.setPosHpr(x, y, z, h, p, r)
        self.sendUpdate('setSmPosHpr', [x, y, z, h, p, r, timestamp])
        if final:
            self.catalogItem.posHpr = (x, y, z, h, p, r)
            self.furnitureMgr.itemMoved(self)
            self.mode, self.modeAvId = HouseGlobals.FURNITURE_MODE_STOP, avId
            self.sendUpdate('setMode', [self.mode, self.modeAvId])
        elif self.mode != HouseGlobals.FURNITURE_MODE_START:
            self.mode, self.modeAvId = HouseGlobals.FURNITURE_MODE_START, avId
            self.sendUpdate('setMode', [self.mode, self.modeAvId])
