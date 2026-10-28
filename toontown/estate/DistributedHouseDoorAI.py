from direct.directnotify import DirectNotifyGlobal
from toontown.building.DistributedDoorAI import DistributedDoorAI
from toontown.building import DoorTypes


class DistributedHouseDoorAI(DistributedDoorAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedHouseDoorAI')

    def __init__(self, air, houseId, doorType):
        DistributedDoorAI.__init__(self, air, houseId, doorType)
