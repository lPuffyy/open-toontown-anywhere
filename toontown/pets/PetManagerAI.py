import random
import time
import traceback
from direct.directnotify import DirectNotifyGlobal
from toontown.pets import PetUtil, PetTraits, PetMood
from toontown.pets.PetNameGenerator import PetNameGenerator

class PetManagerAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('PetManagerAI')

    SPAWN_DELAY = 8.0        # seconds a toon must have been here before its pet is generated (see __watchToonsBody)

    def __init__(self, air):
        self.air = air
        self.arrived = {}        # avId -> when this district first saw the toon
        self.pets = {}           # avId -> DistributedPetAI currently out with its owner
        self.loading = set()     # avIds whose pet is being read from the database
        self.lastSave = 0.0
        taskMgr.doMethodLater(4.0, self.__watchToons, 'petMgrWatchToons')

    def savePet(self, pet):
        """Write the pet's moods, tricks and last-seen time back to the database."""
        try:
            fields = {'setLastSeenTimestamp': (int(time.time()),), 'setTrickAptitudes': (list(pet.getTrickAptitudes()),)}
            for comp in PetMood.PetMood.Components:
                fields['set' + comp[0].upper() + comp[1:]] = (float(getattr(pet, 'get' + comp[0].upper() + comp[1:])()),)
            self.air.dbInterface.updateObject(self.air.dbId, pet.doId, self.air.dclassesByName['DistributedPetAI'], fields)
        except Exception:
            self.notify.warning('could not save pet %s' % pet.doId)

    def __canHavePet(self, zoneId, petOwnerId = None):
        """Pets come along in playgrounds and out in an estate's grounds, never into a house. In someone else's estate a pet may only
        stay while that estate's owner is out in the grounds too (the owner's own doodle is there whenever the owner is)."""
        from toontown.hood import ZoneUtil
        if ZoneUtil.isPlayground(zoneId):
            return True
        estateMgr = getattr(self.air, 'estateMgr', None)
        if estateMgr is None:
            return False
        ownerId = estateMgr.getOwnerFromZone(zoneId)
        if not ownerId or zoneId in estateMgr.getEstateHouseZones(ownerId):
            return False
        if petOwnerId is None or petOwnerId == ownerId:
            return True
        host = self.air.doId2do.get(ownerId)
        return host is not None and host.zoneId in estateMgr.getEstateZones(ownerId)

    def __watchToons(self, task):
        # a pet bug must never take the district down: log it and try again on the next tick
        try:
            self.__watchToonsBody()
        except Exception:
            self.notify.warning('pet watch failed: ' + traceback.format_exc())
        return task.again

    def __watchToonsBody(self):
        """Keep each owner's pet next to them while they are in a playground; remove it when they leave."""
        for avId, pet in list(self.pets.items()):
            av = self.air.doId2do.get(avId)
            if av is None or av.getPetId() != pet.doId or av.zoneId != pet.zoneId or not self.__canHavePet(av.zoneId, avId):
                self.pets.pop(avId, None)
                if not pet.isDeleted():
                    self.savePet(pet)
                    pet.requestDelete()
        now = time.time()
        here = set()
        for av in list(self.air.doId2do.values()):
            if av.__class__.__name__ != 'DistributedToonAI' or not hasattr(av, 'getPetId'):
                continue
            here.add(av.doId)
            petId = av.getPetId()
            firstSeen = self.arrived.setdefault(av.doId, now)
            # A doodle has one id for the whole game, but every district can generate it. A toon who has just come from another
            # district still has its pet there for a few seconds (that district removes it on its next look); generating it here
            # first lets the other district's delete take the new one away, leaving a pet that exists only in this district's memory.
            if now - firstSeen < self.SPAWN_DELAY:
                continue
            if petId and av.doId not in self.pets and av.doId not in self.loading and self.__canHavePet(av.zoneId, av.doId):
                self.loading.add(av.doId)
                self.__spawn(av.doId, petId, av.zoneId)
        for avId in list(self.arrived):
            if avId not in here:
                del self.arrived[avId]
        if now - self.lastSave > 60.0:
            self.lastSave = now
            for pet in list(self.pets.values()):
                self.savePet(pet)

    def __spawn(self, avId, petId, zoneId):
        from toontown.pets import DistributedPetAI

        def got(dclass, fields):
            try:
                gotPet(dclass, fields)
            except Exception:
                self.loading.discard(avId)
                self.notify.warning('could not spawn the pet of %s: %s' % (avId, traceback.format_exc()))

        def gotPet(dclass, fields):
            self.loading.discard(avId)
            av = self.air.doId2do.get(avId)
            if fields is None or av is None or av.zoneId != zoneId or avId in self.pets:
                return

            def f(name, default=0):
                v = fields.get(name)
                return v[0] if v else default
            dna = [f('setHead', -1), f('setEars', -1), f('setNose', -1), f('setTail', -1), f('setBodyTexture'),
                   f('setColor'), f('setColorScale'), f('setEyeColor'), f('setGender')]
            stale = self.air.doId2do.get(petId)
            if stale is not None and stale not in self.pets.values():
                # left behind by an earlier delete that never finished: clear it so the pet can be generated again
                self.notify.warning('clearing a stale pet %s before spawning it for %s' % (petId, avId))
                try:
                    self.air.removeDOFromTables(stale)
                    stale.delete()
                except Exception:
                    self.notify.warning('could not clear the stale pet %s: %s' % (petId, traceback.format_exc()))
            pet = DistributedPetAI.DistributedPetAI(self.air)
            # the look has to be on the pet before it is generated: a client builds the doodle's model from the values it is told at that
            # moment, and applying them afterwards (what the dna argument does) leaves every doodle default white
            pet.setHead(dna[0])
            pet.setEars(dna[1])
            pet.setNose(dna[2])
            pet.setTail(dna[3])
            pet.setBodyTexture(dna[4])
            pet.setColor(dna[5])
            pet.setColorScale(dna[6])
            pet.setEyeColor(dna[7])
            pet.setGender(dna[8])
            pet.setOwnerId(avId)
            pet.setPetName(f('setPetName', 'Doodle'))
            pet.setTraitSeed(f('setTraitSeed'))
            pet.setSafeZone(f('setSafeZone', zoneId))
            pet.setLastSeenTimestamp(f('setLastSeenTimestamp', int(time.time())))
            for comp in PetMood.PetMood.Components:
                pet.requiredMoodComponents[comp] = f('set' + comp[0].upper() + comp[1:], 0.0)
            apt = fields.get('setTrickAptitudes')
            if apt:
                pet.trickAptitudes = list(apt[0])
            pet.generateWithRequiredAndId(petId, self.air.districtId, zoneId)
            self.pets[avId] = pet

        self.air.dbInterface.queryObject(self.air.dbId, petId, got)

    def getAvailablePets(self, numPets, numClerks=1):
        """Seeds for the pets on offer; the same all day, new ones tomorrow."""
        day = int(time.time() // 86400)
        rng = random.Random(day)
        return sorted(rng.randint(0, 2 ** 20) for _ in range(numPets))

    def createNewPetFromSeed(self, avId, seed, nameIndex, gender, safeZoneId):
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        name, dna, traitSeed = PetUtil.getPetInfoFromSeed(seed, safeZoneId)
        name = PetNameGenerator().getName(nameIndex)
        head, ears, nose, tail, body, color, colorScale, eyes, _ = dna
        traits = PetTraits.PetTraits(traitSeed, safeZoneId)
        fields = {'setOwnerId': (avId,), 'setPetName': (name,), 'setTraitSeed': (traitSeed,), 'setSafeZone': (safeZoneId,),
                  'setHead': (head,), 'setEars': (ears,), 'setNose': (nose,), 'setTail': (tail,), 'setBodyTexture': (body,),
                  'setColor': (color,), 'setColorScale': (colorScale,), 'setEyeColor': (eyes,), 'setGender': (gender,),
                  'setLastSeenTimestamp': (int(time.time()),), 'setTrickAptitudes': ([],)}
        for traitName in PetTraits.getTraitNames():
            fields['set' + traitName[0].upper() + traitName[1:]] = (traits.getTraitValue(traitName),)
        for comp in PetMood.PetMood.Components:
            fields['set' + comp[0].upper() + comp[1:]] = (0.0,)

        def created(petId):
            if not petId:
                self.notify.warning('could not create a pet for %s' % avId)
                return
            owner = self.air.doId2do.get(avId)
            if owner:
                owner.b_setPetId(petId)

        self.air.dbInterface.createObject(self.air.dbId, self.air.dclassesByName['DistributedPetAI'], fields, created)

    def deleteToonsPet(self, avId):
        av = self.air.doId2do.get(avId)
        if av is not None and av.getPetId() != 0:
            av.b_setPetId(0)
