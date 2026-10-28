from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.catalog import CatalogItem, CatalogItemList, CatalogFurnitureItem
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.estate.DistributedClosetAI import DistributedClosetAI
from toontown.estate.DistributedBankAI import DistributedBankAI
from toontown.estate.DistributedPhoneAI import DistributedPhoneAI

OK = 0
BAD_INDEX = -1
NOT_FOUND = -2
NO_PERMISSION = -3
STORE = CatalogItem.Customization | CatalogItem.Location


def blobOf(items, store=CatalogItem.Customization):
    return CatalogItemList.CatalogItemList(items, store=store).getBlob(store)


class DistributedFurnitureManagerAI(DistributedObjectAI):
    """Owns the furniture objects of one house interior, plus the attic, the wallpaper and window lists."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureManagerAI')

    def __init__(self, air, house, interior):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.interior = interior
        self.director = 0
        self.visitors = set()
        self.room = {}                # object doId -> DistributedFurnitureItemAI
        self.attic = []               # catalog items stored away
        self.deleted = []
        self.atticWallpaper = []
        self.atticWindows = []

    # ---- required fields -------------------------------------------------------------------------------------------
    def getOwnerId(self):
        return self.house.ownerId

    def getOwnerName(self):
        return self.house.name

    def getInteriorId(self):
        return self.interior.doId

    def getAtticItems(self):
        return blobOf(self.attic)

    def getAtticWallpaper(self):
        return blobOf(self.atticWallpaper)

    def getAtticWindows(self):
        return blobOf(self.atticWindows)

    def getDeletedItems(self):
        return blobOf(self.deleted)

    # ---- building the room -------------------------------------------------------------------------------------------
    def loadFurniture(self, items):
        for item in items:
            self.__spawn(item)

    def __spawn(self, item):
        flags = item.getFlags()
        if flags & CatalogFurnitureItem.FLCloset:
            obj = DistributedClosetAI(self.air, self, item)
        elif flags & CatalogFurnitureItem.FLBank:
            obj = DistributedBankAI(self.air, self, item)
        elif flags & CatalogFurnitureItem.FLPhone:
            obj = DistributedPhoneAI(self.air, self, item)
        else:
            obj = DistributedFurnitureItemAI(self.air, self, item)
        obj.generateWithRequired(self.zoneId)
        obj.placeInRoom()
        self.room[obj.doId] = obj
        return obj

    def itemMoved(self, obj):
        self.house.saveInterior([o.catalogItem for o in self.room.values()])

    def destroy(self):
        for obj in list(self.room.values()):
            obj.requestDelete()
        self.room = {}
        if not self.isDeleted():
            self.requestDelete()

    # ---- director (the one toon who may rearrange) -------------------------------------------------------------------
    def suggestDirector(self, avId):
        sender = self.air.getAvatarIdFromSender()
        if sender != self.house.ownerId:
            return
        if avId and avId != sender:
            return
        self.director = avId
        self.sendUpdate('setDirector', [avId])

    def avatarEnter(self):
        self.visitors.add(self.air.getAvatarIdFromSender())

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        self.visitors.discard(avId)
        if avId == self.director:
            self.director = 0
            self.sendUpdate('setDirector', [0])

    def __isDirector(self):
        return self.air.getAvatarIdFromSender() == self.director and self.director != 0

    def __update(self, field, value):
        self.sendUpdate(field, [value])

    # ---- furniture ---------------------------------------------------------------------------------------------------
    def moveItemToAtticMessage(self, doId, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector():
            return self.sendUpdateToAvatarId(sender, 'moveItemToAtticResponse', [NO_PERMISSION, context])
        obj = self.room.pop(doId, None)
        if obj is None:
            return self.sendUpdateToAvatarId(sender, 'moveItemToAtticResponse', [NOT_FOUND, context])
        self.attic.append(obj.catalogItem)
        obj.requestDelete()
        self.__update('setAtticItems', blobOf(self.attic))
        self.house.saveInterior([o.catalogItem for o in self.room.values()])
        self.sendUpdateToAvatarId(sender, 'moveItemToAtticResponse', [OK, context])

    def moveItemFromAtticMessage(self, index, x, y, z, h, p, r, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector():
            return self.sendUpdateToAvatarId(sender, 'moveItemFromAtticResponse', [NO_PERMISSION, 0, context])
        if index < 0 or index >= len(self.attic):
            return self.sendUpdateToAvatarId(sender, 'moveItemFromAtticResponse', [BAD_INDEX, 0, context])
        item = self.attic.pop(index)
        item.posHpr = (x, y, z, h, p, r)
        obj = self.__spawn(item)
        self.__update('setAtticItems', blobOf(self.attic))
        self.house.saveInterior([o.catalogItem for o in self.room.values()])
        self.sendUpdateToAvatarId(sender, 'moveItemFromAtticResponse', [OK, obj.doId, context])

    def deleteItemFromAtticMessage(self, blob, index, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector() or index < 0 or index >= len(self.attic):
            return self.sendUpdateToAvatarId(sender, 'deleteItemFromAtticResponse', [BAD_INDEX, context])
        self.deleted.append(self.attic.pop(index))
        self.__update('setAtticItems', blobOf(self.attic))
        self.__update('setDeletedItems', blobOf(self.deleted))
        self.sendUpdateToAvatarId(sender, 'deleteItemFromAtticResponse', [OK, context])

    def deleteItemFromRoomMessage(self, blob, doId, context):
        sender = self.air.getAvatarIdFromSender()
        obj = self.room.pop(doId, None)
        if not self.__isDirector() or obj is None:
            return self.sendUpdateToAvatarId(sender, 'deleteItemFromRoomResponse', [NOT_FOUND, context])
        self.deleted.append(obj.catalogItem)
        obj.requestDelete()
        self.__update('setDeletedItems', blobOf(self.deleted))
        self.house.saveInterior([o.catalogItem for o in self.room.values()])
        self.sendUpdateToAvatarId(sender, 'deleteItemFromRoomResponse', [OK, context])

    def recoverDeletedItemMessage(self, blob, index, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector() or index < 0 or index >= len(self.deleted):
            return self.sendUpdateToAvatarId(sender, 'recoverDeletedItemResponse', [BAD_INDEX, context])
        self.attic.append(self.deleted.pop(index))
        self.__update('setAtticItems', blobOf(self.attic))
        self.__update('setDeletedItems', blobOf(self.deleted))
        self.sendUpdateToAvatarId(sender, 'recoverDeletedItemResponse', [OK, context])

    # ---- wallpaper and windows ---------------------------------------------------------------------------------------
    def __save(self):
        self.house.saveInterior([o.catalogItem for o in self.room.values()])

    def __wallpaperUpdated(self):
        self.__update('setAtticWallpaper', blobOf(self.atticWallpaper))
        self.__save()

    def __windowsUpdated(self):
        self.interior.d_updateWindows()
        self.__update('setAtticWindows', blobOf(self.atticWindows))
        self.__save()

    def moveWallpaperFromAtticMessage(self, index, room, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector():
            return self.sendUpdateToAvatarId(sender, 'moveWallpaperFromAtticResponse', [NO_PERMISSION, context])
        if index < 0 or index >= len(self.atticWallpaper) or room not in (0, 1):
            return self.sendUpdateToAvatarId(sender, 'moveWallpaperFromAtticResponse', [BAD_INDEX, context])
        item = self.atticWallpaper.pop(index)
        old = self.interior.swapSurface(item, room)
        if old is not None:
            self.atticWallpaper.append(old)
        self.__wallpaperUpdated()
        self.sendUpdateToAvatarId(sender, 'moveWallpaperFromAtticResponse', [OK, context])

    def deleteWallpaperFromAtticMessage(self, blob, index, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector() or index < 0 or index >= len(self.atticWallpaper):
            return self.sendUpdateToAvatarId(sender, 'deleteWallpaperFromAtticResponse', [BAD_INDEX, context])
        del self.atticWallpaper[index]
        self.__wallpaperUpdated()
        self.sendUpdateToAvatarId(sender, 'deleteWallpaperFromAtticResponse', [OK, context])

    def moveWindowToAtticMessage(self, slot, context):
        sender = self.air.getAvatarIdFromSender()
        win = self.interior.windowAt(slot)
        if not self.__isDirector() or win is None:
            return self.sendUpdateToAvatarId(sender, 'moveWindowToAtticResponse', [BAD_INDEX, context])
        self.interior.windows.remove(win)
        win.placement = None
        self.atticWindows.append(win)
        self.__windowsUpdated()
        self.sendUpdateToAvatarId(sender, 'moveWindowToAtticResponse', [OK, context])

    def moveWindowFromAtticMessage(self, index, slot, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector() or index < 0 or index >= len(self.atticWindows):
            return self.sendUpdateToAvatarId(sender, 'moveWindowFromAtticResponse', [BAD_INDEX, context])
        item = self.atticWindows.pop(index)
        old = self.interior.windowAt(slot)
        if old is not None:
            self.interior.windows.remove(old)
            old.placement = None
            self.atticWindows.append(old)
        item.placement = slot
        self.interior.windows.append(item)
        self.__windowsUpdated()
        self.sendUpdateToAvatarId(sender, 'moveWindowFromAtticResponse', [OK, context])

    def moveWindowMessage(self, fromSlot, toSlot, context):
        sender = self.air.getAvatarIdFromSender()
        win = self.interior.windowAt(fromSlot)
        if not self.__isDirector() or win is None:
            return self.sendUpdateToAvatarId(sender, 'moveWindowResponse', [BAD_INDEX, context])
        other = self.interior.windowAt(toSlot)
        if other is not None:
            other.placement = fromSlot
        win.placement = toSlot
        self.__windowsUpdated()
        self.sendUpdateToAvatarId(sender, 'moveWindowResponse', [OK, context])

    def deleteWindowFromAtticMessage(self, blob, index, context):
        sender = self.air.getAvatarIdFromSender()
        if not self.__isDirector() or index < 0 or index >= len(self.atticWindows):
            return self.sendUpdateToAvatarId(sender, 'deleteWindowFromAtticResponse', [BAD_INDEX, context])
        del self.atticWindows[index]
        self.__windowsUpdated()
        self.sendUpdateToAvatarId(sender, 'deleteWindowFromAtticResponse', [OK, context])
