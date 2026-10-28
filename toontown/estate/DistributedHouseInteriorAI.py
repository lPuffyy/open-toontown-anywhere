from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.catalog import CatalogItem, CatalogItemList
from toontown.catalog.CatalogWallpaperItem import CatalogWallpaperItem
from toontown.catalog.CatalogMouldingItem import CatalogMouldingItem
from toontown.catalog.CatalogFlooringItem import CatalogFlooringItem
from toontown.catalog.CatalogWainscotingItem import CatalogWainscotingItem

SURFACE_STORE = CatalogItem.Customization
WINDOW_STORE = CatalogItem.Customization | CatalogItem.WindowPlacement
SURFACES_PER_ROOM = 4


def defaultSurfaces():
    """The starter walls for both rooms (wallpaper, moulding, flooring, wainscoting, twice): striped paper with a diamond border, wood floor."""
    one = [CatalogWallpaperItem(1110, 0, 1010, 0), CatalogMouldingItem(1000, 2), CatalogFlooringItem(1000, 4), CatalogWainscotingItem(1010, 4)]
    return one + [CatalogWallpaperItem(1110, 0, 1010, 0), CatalogMouldingItem(1000, 2), CatalogFlooringItem(1000, 4), CatalogWainscotingItem(1010, 4)]


class DistributedHouseInteriorAI(DistributedObjectAI):
    """The walls, floors and windows of a house. The surfaces are a list of 4 items per room (wallpaper, moulding, flooring,
    wainscoting); windows are items whose placement says which wall slot they hang in."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedHouseInteriorAI')

    def __init__(self, air, houseId, houseIndex, surfaces=None, windows=None):
        DistributedObjectAI.__init__(self, air)
        self.houseId = houseId
        self.houseIndex = houseIndex
        self.surfaces = list(surfaces) if surfaces else defaultSurfaces()
        self.windows = list(windows) if windows else []

    def getHouseId(self):
        return self.houseId

    def getHouseIndex(self):
        return self.houseIndex

    def surfaceBlob(self):
        return CatalogItemList.CatalogItemList(self.surfaces, store=SURFACE_STORE).getBlob(SURFACE_STORE)

    def windowBlob(self):
        return CatalogItemList.CatalogItemList(self.windows, store=WINDOW_STORE).getBlob(WINDOW_STORE)

    def getWallpaper(self):
        return self.surfaceBlob()

    def getWindows(self):
        return self.windowBlob()

    def d_updateSurfaces(self):
        self.sendUpdate('setWallpaper', [self.surfaceBlob()])

    def d_updateWindows(self):
        self.sendUpdate('setWindows', [self.windowBlob()])

    def swapSurface(self, item, room):
        """Hangs `item` in `room`; returns the item it replaced."""
        slot = room * SURFACES_PER_ROOM + item.getSurfaceType()
        if slot < 0 or slot >= len(self.surfaces):
            return None
        old = self.surfaces[slot]
        self.surfaces[slot] = item
        self.d_updateSurfaces()
        return old

    def windowAt(self, slot):
        for w in self.windows:
            if w.placement == slot:
                return w
        return None
