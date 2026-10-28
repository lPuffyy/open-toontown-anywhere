import random
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.estate.DistributedEstateAI import DistributedEstateAI
from toontown.estate.DistributedHouseAI import DistributedHouseAI
from toontown.toonbase import ToontownGlobals

EMPTY_ESTATE_LINGER = 30.0


class EstateManagerAI(DistributedObjectAI):
    """Hands out estates. Each toon that goes home (or visits a friend) gets an estate zone with a house in it
    and a second zone for the house interior. Estates are created on demand and torn down once nobody is left."""
    notify = DirectNotifyGlobal.directNotify.newCategory('EstateManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.estate = {}          # ownerId -> DistributedEstateAI
        self.houses = {}          # ownerId -> [DistributedHouseAI]
        self.fishing = {}         # ownerId -> pond, docks (and, through the pond, fish targets)
        self.gardens = {}         # ownerId -> EstateGarden
        self.dna = None
        self.zone2owner = {}      # estate or house-interior zone -> ownerId
        self.owner2zones = {}     # ownerId -> [estate zone, interior zones...]
        self.owner2houseZones = {}
        self.visitors = {}        # ownerId -> set(avId)
        self.avId2owner = {}

    # ---- lookups other parts of the AI use -------------------------------------------------------------------------
    def getOwnerFromZone(self, zoneId):
        return self.zone2owner.get(zoneId)

    def getEstateZones(self, ownerId):
        return list(self.owner2zones.get(ownerId, []))

    def getEstateHouseZones(self, ownerId):
        return list(self.owner2houseZones.get(ownerId, []))

    # ---- client requests ---------------------------------------------------------------------------------------------
    def getEstateZone(self, ownerId, name):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        if ownerId == avId:
            owner = av
        else:
            owner = self.air.doId2do.get(ownerId)
            if owner is None or ownerId not in self.estate and not self.__isFriend(av, ownerId):
                self.sendUpdateToAvatarId(avId, 'setEstateZone', [0, 0])
                return
        if ownerId not in self.estate:
            self.__createEstate(owner)
        self.__addVisitor(ownerId, avId)
        zoneId = self.estate[ownerId].zoneId
        self.sendUpdateToAvatarId(avId, 'setEstateZone', [ownerId, zoneId])
        if hasattr(av, 'enterEstate'):
            try:
                av.enterEstate(ownerId, zoneId)
            except Exception:
                self.notify.warning('enterEstate failed for %s' % avId)

    def __isFriend(self, av, ownerId):
        try:
            return ownerId in [f[0] if isinstance(f, (tuple, list)) else f for f in av.getFriendsList()]
        except Exception:
            return True

    def exitEstate(self):
        avId = self.air.getAvatarIdFromSender()
        self.__removeVisitor(avId)

    def removeFriend(self, ownerId, avId):
        sender = self.air.getAvatarIdFromSender()
        if sender != ownerId:
            return
        self.sendUpdateToAvatarId(avId, 'sendAvToPlayground', [avId, 0])

    # ---- estate life cycle -------------------------------------------------------------------------------------------
    def __createEstate(self, owner):
        ownerId = owner.doId
        estateZone = self.air.allocateZone(ownerId)
        interiorZone = self.air.allocateZone(ownerId)
        self.zone2owner[estateZone] = ownerId
        self.zone2owner[interiorZone] = ownerId
        self.owner2zones[ownerId] = [estateZone, interiorZone]
        self.owner2houseZones[ownerId] = [interiorZone]

        estate = DistributedEstateAI(self.air, ownerId)
        estate.generateWithRequired(estateZone)
        self.estate[ownerId] = estate

        self.fishing[ownerId] = self.__createFishing(estateZone)
        self.__createGarden(owner, estate, estateZone)

        house = DistributedHouseAI(self.air, owner, estateZone, interiorZone, housePos=0)
        house.generate_all()
        self.houses[ownerId] = [house]
        estate.houses = self.houses[ownerId]
        owner.b_setHouseId(house.doId)
        self.notify.info('created estate %s (zone %s) for toon %s' % (estate.doId, estateZone, ownerId))

    def __createGarden(self, owner, estate, estateZone):
        """Planting spots and flower beds. The owner is given a garden (shovel and can) the first time."""
        try:
            from toontown.estate.GardenAI import EstateGarden
            if not owner.getGardenStarted():
                owner.b_setGardenStarted(1)
            estate.sendUpdate('setIdList', [[owner.doId, 0, 0, 0, 0, 0]])
            self.gardens[owner.doId] = EstateGarden(self.air, owner.doId, estateZone)
        except Exception:
            import traceback
            self.notify.warning('could not make the estate garden: %s' % traceback.format_exc())

    def __estateDNA(self):
        if self.dna is None:
            from toontown.ai.ToontownAIRepository import DNAStorage
            self.dna = self.air.loadDNAFileAI(DNAStorage(), 'phase_5.5/dna/estate_1.dna')
        return self.dna

    def __createFishing(self, estateZone):
        """The estate's pond, its docks and the fish, read from the estate's DNA like a playground's."""
        made = []
        try:
            from toontown.ai.ToontownAIRepository import DNAVisGroup
            from toontown.fishing.DistributedFishingPondAI import DistributedFishingPondAI

            def walk(node):
                if 'fishing_pond' in node.getName():
                    pond = DistributedFishingPondAI(self.air)
                    pond.setArea(ToontownGlobals.MyEstate)
                    pond.generateWithRequired(estateZone)
                    pond.createTargets()
                    made.append(pond)
                    made.extend(self.air.findFishingSpots(node, pond))
                    return
                for i in range(node.getNumChildren()):
                    walk(node.at(i))
            walk(self.__estateDNA())
        except Exception:
            import traceback
            self.notify.warning('could not make the estate pond: %s' % traceback.format_exc())
        return made

    def __addVisitor(self, ownerId, avId):
        self.__removeVisitor(avId)
        self.visitors.setdefault(ownerId, set()).add(avId)
        self.avId2owner[avId] = ownerId
        taskMgr.remove(self.uniqueName('linger-%d' % ownerId))
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__removeVisitor, [avId])

    def __removeVisitor(self, avId):
        ownerId = self.avId2owner.pop(avId, None)
        if ownerId is None:
            return
        self.ignore(self.air.getAvatarExitEvent(avId))
        group = self.visitors.get(ownerId)
        if group is not None:
            group.discard(avId)
            if not group:
                taskMgr.doMethodLater(EMPTY_ESTATE_LINGER, self.__destroyEstate, self.uniqueName('linger-%d' % ownerId), [ownerId])

    def __destroyEstate(self, ownerId):
        if self.visitors.get(ownerId):
            return
        self.visitors.pop(ownerId, None)
        garden = self.gardens.pop(ownerId, None)
        if garden is not None:
            garden.destroy()
        for obj in self.fishing.pop(ownerId, []):
            if not obj.isDeleted():
                obj.requestDelete()
        for house in self.houses.pop(ownerId, []):
            house.destroy_all()
        estate = self.estate.pop(ownerId, None)
        if estate is not None:
            estate.requestDelete()
        for zoneId in self.owner2zones.pop(ownerId, []):
            self.zone2owner.pop(zoneId, None)
            self.air.deallocateZone(zoneId)
        self.owner2houseZones.pop(ownerId, None)
        self.notify.info('removed estate of toon %s' % ownerId)
