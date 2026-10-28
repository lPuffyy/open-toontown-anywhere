import os
import pickle
import random
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.building import DoorTypes
from toontown.estate.DistributedHouseDoorAI import DistributedHouseDoorAI
from toontown.estate.DistributedHouseInteriorAI import DistributedHouseInteriorAI
from toontown.estate import HouseGlobals
from toontown.estate.DistributedFurnitureManagerAI import DistributedFurnitureManagerAI
from toontown.estate.DistributedMailboxAI import DistributedMailboxAI
from toontown.catalog import CatalogItem, CatalogItemList
from toontown.catalog.CatalogFurnitureItem import CatalogFurnitureItem
from toontown.catalog.CatalogWindowItem import CatalogWindowItem

SAVE_DIR = 'estate_data'
STORE = CatalogItem.Customization | CatalogItem.Location
WINDOW_STORE = CatalogItem.Customization | CatalogItem.WindowPlacement


class DistributedHouseAI(DistributedObjectAI):
    """One toon's house in an estate: the outside (this object plus its door) and the inside zone."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedHouseAI')

    def __init__(self, air, owner, estateZone, interiorZone, housePos=0):
        DistributedObjectAI.__init__(self, air)
        self.owner = owner
        self.ownerId = owner.doId
        self.estateZone = estateZone
        self.interiorZone = interiorZone
        self.housePos = housePos
        self.houseType = HouseGlobals.HOUSE_DEFAULT
        self.gardenPos = housePos
        self.name = owner.getName()
        # a house keeps its colour: it comes from the owner, not from a dice roll every time the house is built
        self.color = owner.doId % len(HouseGlobals.houseColors)
        self.interiorWallpaper = b''
        self.interiorWindows = b''
        self.deletedItems = b''
        self.cannonEnabled = 0
        self.extDoor = None
        self.intDoor = None
        self.interior = None
        self.furnitureMgr = None
        self.mailbox = None

    # required fields
    def getHousePos(self):
        return self.housePos

    def getHouseType(self):
        return self.houseType

    def getGardenPos(self):
        return self.gardenPos

    def getAvatarId(self):
        return self.ownerId

    def getName(self):
        return self.name

    def getColor(self):
        return self.color

    def setColor(self, c):
        self.color = c
        self.sendUpdate('setColor', [c])

    # the lists the catalog code counts (len) and adds to; they live in the furniture manager once the interior exists
    @property
    def atticItems(self):
        return self.furnitureMgr.attic if self.furnitureMgr else []

    @property
    def interiorItems(self):
        return [o.catalogItem for o in self.furnitureMgr.room.values()] if self.furnitureMgr else []

    @property
    def atticWallpaper(self):
        return self.furnitureMgr.atticWallpaper if self.furnitureMgr else []

    @property
    def atticWindows(self):
        return self.furnitureMgr.atticWindows if self.furnitureMgr else []

    def getAtticItems(self):
        return CatalogItemList.CatalogItemList(self.atticItems, store=CatalogItem.Customization).getBlob(CatalogItem.Customization)

    def getInteriorItems(self):
        return CatalogItemList.CatalogItemList(self.interiorItems, store=STORE).getBlob(STORE)

    def getAtticWallpaper(self):
        return CatalogItemList.CatalogItemList(self.atticWallpaper, store=CatalogItem.Customization).getBlob(CatalogItem.Customization)

    def getInteriorWallpaper(self):
        return self.interiorWallpaper

    def getAtticWindows(self):
        return CatalogItemList.CatalogItemList(self.atticWindows, store=CatalogItem.Customization).getBlob(CatalogItem.Customization)

    # the catalog's recordPurchase calls these when an accepted mailbox item belongs in the house
    def addAtticItem(self, item):
        self.furnitureMgr.attic.append(item)
        self.furnitureMgr.sendUpdate('setAtticItems', [self.getAtticItems()])
        self.saveInterior(self.interiorItems)

    def addWallpaper(self, item):
        self.furnitureMgr.atticWallpaper.append(item)
        self.furnitureMgr.sendUpdate('setAtticWallpaper', [self.getAtticWallpaper()])
        self.saveInterior(self.interiorItems)

    def addWindow(self, item):
        self.furnitureMgr.atticWindows.append(item)
        self.furnitureMgr.sendUpdate('setAtticWindows', [self.getAtticWindows()])
        self.saveInterior(self.interiorItems)

    def getInteriorWindows(self):
        return self.interiorWindows

    def getDeletedItems(self):
        return self.deletedItems

    def getCannonEnabled(self):
        return self.cannonEnabled

    # building the house -------------------------------------------------------------------------------------------
    def generate_all(self):
        self.generateWithRequired(self.estateZone)
        self.sendUpdate('setHouseReady', [])
        self.extDoor = DistributedHouseDoorAI(self.air, self.doId, DoorTypes.EXT_STANDARD)
        self.intDoor = DistributedHouseDoorAI(self.air, self.doId, DoorTypes.INT_STANDARD)
        self.extDoor.setOtherDoor(self.intDoor)
        self.intDoor.setOtherDoor(self.extDoor)
        self.extDoor.zoneId = self.estateZone
        self.intDoor.zoneId = self.interiorZone
        self.extDoor.generateWithRequired(self.estateZone)
        self.intDoor.generateWithRequired(self.interiorZone)
        saved = self.__loadSaved()
        if saved and self.__isOldStarterRoom(saved):
            saved = {}                                   # an untouched old starter house gets the new starter room, walls and windows
        surfaces = windows = None
        try:
            surfaces = list(CatalogItemList.CatalogItemList(saved.get('surfaces', b''), store=CatalogItem.Customization))
            windows = list(CatalogItemList.CatalogItemList(saved.get('placedWindows', b''), store=WINDOW_STORE))
        except Exception:
            pass
        if not windows:
            windows = [CatalogWindowItem(20, placement=2), CatalogWindowItem(20, placement=4)]
        self.interior = DistributedHouseInteriorAI(self.air, self.doId, self.housePos, surfaces, windows)
        self.interior.generateWithRequired(self.interiorZone)
        self.makeFurniture(saved)

    def __savePath(self):
        return os.path.join(SAVE_DIR, '%d.pickle' % self.ownerId)

    # The starter room every new toon gets (the layout the original game's starter houses use): a bed, closet, bank and phone along the
    # west wall, a lounge with a cabinet, couches and three armchairs, and rugs. (id, x, y, z, heading)
    DEFAULT_LAYOUT = (
        (200, -23, 6, 0, 90),        # bed
        (1200, -21, 9.5, 0, 0),      # end table
        (None, -23, 13, 0, 90),      # closet (boy's or girl's)
        (1300, -4, 23, 0, 320),      # jellybean bank
        (1020, 0, -17.5, 0, 0),      # rug B
        (400, 0, -26, 0, 180),       # fireplace
        (100, 6.3, -12, 0, 315),     # chairs
        (100, 0, -10, 0, 0),
        (100, -6.3, -12, 0, 45),
        (1010, -5.6, 21, 0, 320),    # rug A
        (710, -12, 23, 0, 0),        # two-seat couch
        (1110, 3.1, 0.5, 0, 0),      # cabinet
        (700, -15, -0.5, 0, 0),      # armchair
        (1000, -13, -12, 0, 0),      # rug
        (1399, -11, 2, 0, 0),        # phone
    )

    def __defaultItems(self):
        closet = 510 if self.owner.dna.gender == 'f' else 500
        return [CatalogFurnitureItem(closet if iid is None else iid, posHpr=(x, y, z, h, 0, 0)) for iid, x, y, z, h in self.DEFAULT_LAYOUT]

    def __isOldStarterRoom(self, saved):
        """A saved room that is still the old bare starter (closet, bank, phone and nothing else, nothing in the attic): replace it."""
        try:
            room = list(CatalogItemList.CatalogItemList(saved['room'], store=STORE))
            attic = list(CatalogItemList.CatalogItemList(saved['attic'], store=CatalogItem.Customization))
            return not attic and sorted(i.furnitureType for i in room) == [500 if self.owner.dna.gender != 'f' else 510, 1300, 1399]
        except Exception:
            return False

    def __loadSaved(self):
        try:
            with open(self.__savePath(), 'rb') as f:
                return pickle.load(f)
        except Exception:
            return {}

    def makeFurniture(self, saved):
        room, attic, wallpaper, windows = None, [], [], []
        try:
            room = list(CatalogItemList.CatalogItemList(saved['room'], store=STORE))
            attic = list(CatalogItemList.CatalogItemList(saved['attic'], store=CatalogItem.Customization))
            wallpaper = list(CatalogItemList.CatalogItemList(saved.get('wallpaper', b''), store=CatalogItem.Customization))
            windows = list(CatalogItemList.CatalogItemList(saved.get('windows', b''), store=CatalogItem.Customization))
        except Exception:
            pass
        if room is None:
            room = self.__defaultItems()
        self.furnitureMgr = DistributedFurnitureManagerAI(self.air, self, self.interior)
        self.furnitureMgr.generateWithRequired(self.interiorZone)
        self.furnitureMgr.attic = attic
        self.furnitureMgr.atticWallpaper = wallpaper
        self.furnitureMgr.atticWindows = windows
        self.furnitureMgr.loadFurniture(room)
        self.mailbox = DistributedMailboxAI(self.air, self)
        self.mailbox.generateWithRequired(self.estateZone)

    def saveInterior(self, roomItems):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            data = {'room': CatalogItemList.CatalogItemList(roomItems, store=STORE).getBlob(STORE),
                    'attic': self.getAtticItems(),
                    'wallpaper': self.getAtticWallpaper(),
                    'windows': self.getAtticWindows()}
            if self.interior is not None:
                data['surfaces'] = self.interior.surfaceBlob()
                data['placedWindows'] = self.interior.windowBlob()
            with open(self.__savePath(), 'wb') as f:
                pickle.dump(data, f)
        except Exception:
            self.notify.warning('could not save the interior of house %s' % self.doId)

    def destroy_all(self):
        if self.furnitureMgr is not None:
            self.furnitureMgr.destroy()
        for obj in (self.mailbox, self.interior, self.intDoor, self.extDoor):
            if obj is not None and not obj.isDeleted():
                obj.requestDelete()
        self.furnitureMgr = self.mailbox = self.interior = self.intDoor = self.extDoor = None
        if not self.isDeleted():
            self.requestDelete()
