"""The garden of an estate: plots the owner plants flowers, gag trees and statues in, and the objects that grow there.

An EstateGarden owns one DistributedGardenPlotAI per planting spot of the estate. Planting swaps the plot for a plant object, digging the
plant up swaps the plot back. The state of every spot is saved to estate_data/<ownerId>_garden.json."""
import json
import os
import time
import traceback
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedNodeAI import DistributedNodeAI
from toontown.estate import GardenGlobals
from toontown.estate.FlowerBase import FlowerBase

SAVE_DIR = 'estate_data'
GROWTH_TICK = 30.0           # seconds between growth checks (the real game works in days; this is for testing)
WATER_DECAY_TICKS = 4        # every this many ticks each plant loses a point of water
MOVIE_TIMEOUT = 15.0         # if the client never reports its movie as done
# the statues made after the characters we removed from this build
BLOCKED_STATUARY = ()      # (the four character statues were replaced with a hydrant, mailbox, trash can and fountain)
ACCELERATOR_SPECIES = 202    # the Garden Accelerator statue: while one stands in the garden everything in it grows twice as fast
MAX_OFFLINE_TICKS = 14 * 24 * 120    # growth is simulated for at most two weeks away
PLANT, PLOT, FLOWER, TREE, STATUE, TOON_STATUE = 'plant', 'plot', 'flower', 'tree', 'statue', 'toonstatue'


class LawnDecorAI(DistributedNodeAI):
    """Base of everything standing on a planting spot."""
    notify = DirectNotifyGlobal.directNotify.newCategory('LawnDecorAI')

    def __init__(self, air, garden, index):
        DistributedNodeAI.__init__(self, air)
        self.garden = garden
        self.index = index
        self.afterMovie = None

    def getPlot(self):
        return self.index

    def getHeading(self):
        return self.garden.spots[self.index][2]

    def getPosition(self):
        spot = self.garden.spots[self.index]
        return (spot[0], spot[1], 0.0)

    def getOwnerIndex(self):
        return 0

    def d_movie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def plotEntered(self):
        pass

    def isOwner(self):
        return self.air.getAvatarIdFromSender() == self.garden.ownerId

    def runAfterMovie(self, action):
        """Wait for the client to finish its animation, then do `action` (or do it anyway after a while)."""
        self.afterMovie = action
        taskMgr.remove(self.uniqueName('movieTimeout'))
        taskMgr.doMethodLater(MOVIE_TIMEOUT, lambda task: self.movieDone(), self.uniqueName('movieTimeout'))

    def movieDone(self):
        action, self.afterMovie = self.afterMovie, None
        taskMgr.remove(self.uniqueName('movieTimeout'))
        if action is not None:
            try:
                action()
            except Exception:
                self.notify.warning(traceback.format_exc())

    def delete(self):
        taskMgr.remove(self.uniqueName('movieTimeout'))
        DistributedNodeAI.delete(self)

    def removeItem(self):
        pass


class DistributedGardenBoxAI(DistributedNodeAI):
    """A flower bed: decoration."""

    def __init__(self, air, spot, index, owner):
        DistributedNodeAI.__init__(self, air)
        self.spot = spot
        self.index = index

    def getPlot(self):
        return self.index

    def getHeading(self):
        return self.spot[2]

    def getPosition(self):
        return (self.spot[0], self.spot[1], 0.0)

    def getOwnerIndex(self):
        return 0

    def getTypeIndex(self):
        return self.spot[3]


class DistributedGardenPlotAI(LawnDecorAI):
    """An empty planting spot."""

    def plantFlower(self, species, variety):
        av = self.garden.ownerAv()
        if not self.isOwner() or av is None or self.garden.kindAt(self.index) != GardenGlobals.FLOWER_TYPE:
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, self.air.getAvatarIdFromSender())
        beans = GardenGlobals.getNumBeansRequired(species, variety)
        attrs = GardenGlobals.PlantAttributes.get(species)
        power = GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill())
        if beans < 0 or attrs is None or attrs['plantType'] != GardenGlobals.FLOWER_TYPE or beans > power or av.getTotalMoney() < beans:
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
        av.takeMoney(beans)
        self.__plant({'kind': FLOWER, 'species': species, 'variety': variety, 'water': 0, 'growth': 0}, av.doId)

    def plantGagTree(self, track, level):
        av = self.garden.ownerAv()
        if not self.isOwner() or av is None or self.garden.kindAt(self.index) != GardenGlobals.GAG_TREE_TYPE:
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, self.air.getAvatarIdFromSender())
        power = GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill())
        if not 0 <= level < 7 or level >= power or not av.inventory.numItem(track, level):
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
        av.inventory.setItem(track, level, av.inventory.numItem(track, level) - 1)
        av.d_setInventory(av.inventory.makeNetString())
        self.__plant({'kind': TREE, 'type': GardenGlobals.getTreeTypeIndex(track, level), 'water': 0, 'growth': 0, 'wilted': 0}, av.doId)

    def __recipeSpecial(self, species):
        for key, recipe in GardenGlobals.Recipes.items():
            if GardenGlobals.getSpeciesVarietyGivenRecipe(key)[0] == species:
                return len(recipe['beans']), recipe['special']
        return None, -1

    def plantStatuary(self, species):
        av = self.garden.ownerAv()
        if not self.isOwner() or av is None or self.garden.kindAt(self.index) != GardenGlobals.STATUARY_TYPE or species in BLOCKED_STATUARY:
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, self.air.getAvatarIdFromSender())
        beans, special = self.__recipeSpecial(species)
        owned = dict(av.getGardenSpecials())
        if beans is None or (special >= 0 and not owned.get(special)) or av.getTotalMoney() < beans:
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
        av.takeMoney(beans)
        if special >= 0:
            av.removeGardenItem(special, 1)
        self.__plant({'kind': STATUE, 'species': species}, av.doId)

    def plantToonStatuary(self, species, dnaCode):
        av = self.garden.ownerAv()
        if not self.isOwner() or av is None or self.garden.kindAt(self.index) != GardenGlobals.STATUARY_TYPE:
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, self.air.getAvatarIdFromSender())
        beans, special = self.__recipeSpecial(species)
        owned = dict(av.getGardenSpecials())
        if beans is None or (special >= 0 and not owned.get(special)) or av.getTotalMoney() < beans:
            return self.d_movie(GardenGlobals.MOVIE_PLANT_REJECTED, av.doId)
        av.takeMoney(beans)
        if special >= 0:
            av.removeGardenItem(special, 1)
        self.__plant({'kind': TOON_STATUE, 'species': species, 'optional': dnaCode}, av.doId)

    def plantNothing(self, burntBeans):
        av = self.garden.ownerAv()
        if self.isOwner() and av is not None:
            av.takeMoney(max(0, min(burntBeans, av.getTotalMoney())))

    def __plant(self, data, avId):
        self.d_movie(GardenGlobals.MOVIE_PLANT, avId)
        self.runAfterMovie(lambda: self.garden.plant(self.index, data, avId))


class DistributedPlantBaseAI(LawnDecorAI):
    """A growing thing. Subclasses say what it is."""

    def __init__(self, air, garden, index, data):
        LawnDecorAI.__init__(self, air, garden, index)
        self.data = data
        self.watering = False

    @property
    def attrs(self):
        return GardenGlobals.PlantAttributes[self.getTypeIndex()]

    def getWaterLevel(self):
        return self.data['water']

    def getGrowthLevel(self):
        return self.data['growth']

    def isFruiting(self):
        return self.data['growth'] >= self.attrs['growthThresholds'][2]

    def tick(self, decay, steps = 1):
        """One growth step (or `steps` of them); returns True if anything the clients can see changed."""
        changed = False
        top = self.attrs['growthThresholds'][2]
        if self.data['water'] > 0 and self.data['growth'] < top:
            self.data['growth'] = min(top, self.data['growth'] + steps)
            self.sendUpdate('setGrowthLevel', [self.data['growth']])
            changed = True
        if decay and self.data['water'] > self.attrs['minWaterLevel']:
            self.data['water'] -= 1
            self.sendUpdate('setWaterLevel', [self.data['water']])
            changed = True
        return changed

    def waterPlant(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.garden.ownerId or self.watering:
            return
        power = GardenGlobals.getWateringCanPower(av.getWateringCan(), av.getWateringCanSkill())
        self.watering = True
        self.data['water'] = min(self.attrs['maxWaterLevel'], max(self.data['water'], 0) + power)
        self.sendUpdate('setWaterLevel', [self.data['water']])
        self.d_movie(GardenGlobals.MOVIE_WATER, avId)
        av.b_setWateringCanSkill(av.getWateringCanSkill() + 1)
        self.garden.save()
        taskMgr.remove(self.uniqueName('waterTimeout'))
        taskMgr.doMethodLater(MOVIE_TIMEOUT, lambda task: self.waterPlantDone(), self.uniqueName('waterTimeout'))

    def waterPlantDone(self):
        taskMgr.remove(self.uniqueName('waterTimeout'))
        self.watering = False

    def digUp(self, avId):
        self.d_movie(GardenGlobals.MOVIE_REMOVE, avId)
        self.runAfterMovie(lambda: self.garden.clear(self.index, avId))

    def removeItem(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.garden.ownerId:
            return
        self.digUp(avId)


class DistributedFlowerAI(DistributedPlantBaseAI):
    def getTypeIndex(self):
        return self.data['species']

    def getVariety(self):
        return self.data['variety']

    def removeItem(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.garden.ownerId:
            return
        if self.isFruiting() and self.data['water'] >= 0 and av.addFlowerToBasket(self.data['species'], self.data['variety']):
            flower = FlowerBase(self.data['species'], self.data['variety'])
            if av.flowerCollection.collectFlower(flower) != GardenGlobals.COLLECT_NO_UPDATE:
                av.d_setFlowerCollection(*av.flowerCollection.getNetLists())
            beans = GardenGlobals.getNumBeansRequired(self.data['species'], self.data['variety'])
            if beans == GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill()):
                av.b_setShovelSkill(av.getShovelSkill() + 1)
        self.digUp(avId)


class DistributedGagTreeAI(DistributedPlantBaseAI):
    def getTypeIndex(self):
        return self.data['type']

    def getWilted(self):
        return 1 if self.data['water'] < 0 else 0

    def requestHarvest(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.garden.ownerId or not self.isFruiting() or self.data['water'] < 0:
            return
        track, level = GardenGlobals.getTreeTrackAndLevel(self.data['type'])
        have = av.inventory.numItem(track, level)
        room = av.inventory.getMax(track, level) - have if hasattr(av.inventory, 'getMax') else 1
        gained = max(0, min(2, room))
        if gained:
            av.inventory.setItem(track, level, have + gained)
            av.d_setInventory(av.inventory.makeNetString())
        self.d_movie(GardenGlobals.MOVIE_HARVEST, avId)
        self.data['growth'] = self.attrs['growthThresholds'][1]
        self.data['water'] = 0
        self.sendUpdate('setGrowthLevel', [self.data['growth']])
        self.sendUpdate('setWaterLevel', [0])
        self.garden.save()


class DistributedStatuaryAI(LawnDecorAI):
    def __init__(self, air, garden, index, data):
        LawnDecorAI.__init__(self, air, garden, index)
        self.data = data

    def getTypeIndex(self):
        return self.data['species']

    def getWaterLevel(self):
        return 0

    def getGrowthLevel(self):
        return 0

    def removeItem(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.garden.ownerId:
            return
        self.d_movie(GardenGlobals.MOVIE_REMOVE, avId)
        self.runAfterMovie(lambda: self.garden.clear(self.index, avId))


class DistributedToonStatuaryAI(DistributedStatuaryAI):
    def getOptional(self):
        return self.data.get('optional', 0)


class EstateGarden:
    """All the planting spots of one estate."""
    notify = DirectNotifyGlobal.directNotify.newCategory('EstateGarden')

    def __init__(self, air, ownerId, zoneId):
        self.air = air
        self.ownerId = ownerId
        self.zoneId = zoneId
        self.spots = GardenGlobals.estatePlots[0]
        self.objects = {}            # spot index -> the object standing there
        self.boxes = []
        self.saved = {}              # spot index -> data of what is planted
        self.ticks = 0
        self.taskName = 'garden-%d' % ownerId
        self.load()
        for i in range(len(self.spots)):
            self.__make(i, self.saved.get(i))
        for i, box in enumerate(GardenGlobals.estateBoxes[0]):
            b = DistributedGardenBoxAI(air, box, i, ownerId)
            b.generateWithRequired(zoneId)
            self.boxes.append(b)
        taskMgr.doMethodLater(GROWTH_TICK, self.__tick, self.taskName)

    def ownerAv(self):
        return self.air.doId2do.get(self.ownerId)

    def kindAt(self, index):
        return self.spots[index][3]

    def __savePath(self):
        return os.path.join(SAVE_DIR, '%d_garden.json' % self.ownerId)

    def load(self):
        try:
            with open(self.__savePath()) as f:
                raw = json.load(f)
            elapsed = max(0, time.time() - raw.get('time', time.time()))
            ticks = min(int(elapsed // GROWTH_TICK), MAX_OFFLINE_TICKS)
            for key, data in raw.get('spots', {}).items():
                if 'water' in data and ticks:
                    self.__growWhileAway(data, ticks)
                self.saved[int(key)] = data
        except Exception:
            self.saved = {}

    def __growWhileAway(self, data, ticks):
        """Run the growth ticks that would have happened while nobody was here: watered plants keep growing until the water runs out."""
        index = data.get('species') if data.get('kind') == FLOWER else data.get('type')
        attrs = GardenGlobals.PlantAttributes.get(index)
        if attrs is None:
            return
        top, lowest = attrs['growthThresholds'][2], attrs['minWaterLevel']
        water, growth = data['water'], data.get('growth', 0)
        for i in range(1, ticks + 1):
            if water > 0 and growth < top:
                growth += 1
            if i % WATER_DECAY_TICKS == 0 and water > lowest:
                water -= 1
            if water <= lowest and growth >= top or (water <= 0 and water <= lowest):
                break
        data['water'], data['growth'] = water, growth

    def save(self):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            spots = {str(i): o.data for i, o in self.objects.items() if hasattr(o, 'data')}
            with open(self.__savePath(), 'w') as f:
                json.dump({'time': time.time(), 'spots': spots}, f)
        except Exception:
            self.notify.warning('could not save the garden of %s' % self.ownerId)

    def __make(self, index, data):
        kind = (data or {}).get('kind', PLOT)
        if kind == FLOWER:
            obj = DistributedFlowerAI(self.air, self, index, data)
        elif kind == TREE:
            obj = DistributedGagTreeAI(self.air, self, index, data)
        elif kind == STATUE:
            obj = DistributedStatuaryAI(self.air, self, index, data)
        elif kind == TOON_STATUE:
            obj = DistributedToonStatuaryAI(self.air, self, index, data)
        else:
            obj = DistributedGardenPlotAI(self.air, self, index)
        obj.generateWithRequired(self.zoneId)
        self.objects[index] = obj
        return obj

    def __swap(self, index, data):
        old = self.objects.pop(index, None)
        if old is not None and not old.isDeleted():
            old.requestDelete()
        obj = self.__make(index, data)
        self.save()
        return obj

    def plant(self, index, data, avId):
        obj = self.__swap(index, data)
        obj.d_movie(GardenGlobals.MOVIE_FINISHPLANTING, avId)

    def clear(self, index, avId):
        obj = self.__swap(index, None)
        obj.d_movie(GardenGlobals.MOVIE_FINISHREMOVING, avId)

    def __tick(self, task):
        self.ticks += 1
        decay = self.ticks % WATER_DECAY_TICKS == 0
        changed = False
        boost = 2 if any(getattr(o, 'data', {}).get('species') == ACCELERATOR_SPECIES and getattr(o, 'data', {}).get('kind') == STATUE
                         for o in self.objects.values()) else 1
        for obj in list(self.objects.values()):
            if isinstance(obj, DistributedPlantBaseAI):
                changed = obj.tick(decay, boost) or changed
        if changed:
            self.save()
        return task.again

    def destroy(self):
        taskMgr.remove(self.taskName)
        self.save()
        for obj in list(self.objects.values()) + self.boxes:
            if not obj.isDeleted():
                obj.requestDelete()
        self.objects = {}
        self.boxes = []
