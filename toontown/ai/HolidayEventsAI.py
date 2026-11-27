"""The server side of the holidays (ported from the original game's holiday managers). The holiday manager starts one of these when
its holiday begins and stops it when the holiday ends. Holidays that only change what the clients show have none."""
import json
import random
import time
import traceback
from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from toontown.ai import HolidayBaseAI
from toontown.suit import SuitDNA
from toontown.toonbase import GameConfig
from toontown.toonbase import ToontownGlobals


class BulletinBoardHolidayAI(HolidayBaseAI.HolidayBaseAI):
    """A holiday other code checks for on the bulletin board (bboard)."""
    PostName = None

    def start(self):
        bboard.post(self.PostName, True)

    def stop(self):
        bboard.remove(self.PostName)


class ValentinesDayMgrAI(BulletinBoardHolidayAI):
    PostName = 'ValentinesDay'


class EventObjectHolidayAI(HolidayBaseAI.HolidayBaseAI):
    """A holiday that puts one object in one zone (a shop interior) for players to talk to."""
    PostName = None
    EVENT_ZONE = None

    def objectClass(self):
        raise NotImplementedError

    def start(self):
        self.obj = self.objectClass()(self.air)
        self.obj.generateWithRequired(self.EVENT_ZONE)
        bboard.post(self.PostName)

    def stop(self):
        bboard.remove(self.PostName)
        if self.obj is not None and not self.obj.isDeleted():
            self.obj.requestDelete()
        self.obj = None


class PolarPlaceEventMgrAI(EventObjectHolidayAI):
    PostName = 'polarPlaceEvent'
    EVENT_ZONE = 3821          # Hibernation Vacations

    def objectClass(self):
        from toontown.ai.DistributedPolarPlaceEffectMgrAI import DistributedPolarPlaceEffectMgrAI
        return DistributedPolarPlaceEffectMgrAI


class ResistanceEventMgrAI(EventObjectHolidayAI):
    PostName = 'resistanceEvent'
    EVENT_ZONE = 9720          # Talking in Your Sleep Voiceover Training

    def objectClass(self):
        from toontown.ai.DistributedResistanceEmoteMgrAI import DistributedResistanceEmoteMgrAI
        return DistributedResistanceEmoteMgrAI


class FireworkManagerAI(HolidayBaseAI.HolidayBaseAI):
    """A fireworks holiday: a show in every playground at the top of each hour."""
    notify = DirectNotifyGlobal.directNotify.newCategory('FireworkManagerAI')
    zoneToStyleDict = {ToontownGlobals.DockHarbor: 5,
                       ToontownGlobals.ToontownCentral: 0,
                       ToontownGlobals.TheBrrrgh: 4,
                       ToontownGlobals.MelodyMeadow: 3,
                       ToontownGlobals.GardenGrove: 1,
                       ToontownGlobals.OutdoorZone: 0,
                       ToontownGlobals.SpeedwayPark: 0,
                       ToontownGlobals.SlumberSprings: 2}

    def __init__(self, air, holidayId):
        HolidayBaseAI.HolidayBaseAI.__init__(self, air, holidayId)
        self.fireworkShows = {}
        self.waitTaskName = 'waitStartFireworkShows-%d' % holidayId

    def start(self):
        self.__waitForNextShow()

    def stop(self):
        taskMgr.remove(self.waitTaskName)
        self.stopAllShows()

    def __waitForNextShow(self):
        import time
        now = time.localtime()
        taskMgr.doMethodLater((60 - now[4]) * 60 - now[5], self.__startAllShows, self.waitTaskName)

    def __startAllShows(self, task):
        for hood in self.air.hoods:
            style = self.zoneToStyleDict.get(hood.canonicalHoodId)
            if style is not None:
                self.startShow(hood.zoneId, style)
        self.__waitForNextShow()
        return Task.done

    def startShow(self, zoneId, style=0):
        if zoneId in self.fireworkShows:
            return 0
        from toontown.effects.DistributedFireworkShowAI import DistributedFireworkShowAI
        show = DistributedFireworkShowAI(self.air, self)
        show.generateWithRequired(zoneId)
        self.fireworkShows[zoneId] = show
        show.d_startShow(self.holidayId, style)
        return 1

    def stopShow(self, zoneId):
        show = self.fireworkShows.pop(zoneId, None)
        if show is None:
            return 0
        if not show.isDeleted():
            show.requestDelete()
        return 1

    def stopAllShows(self):
        for zoneId in list(self.fireworkShows):
            self.stopShow(zoneId)

    def isShowRunning(self, zoneId):
        return zoneId in self.fireworkShows


class HolidaySuitInvasionManagerAI(HolidayBaseAI.HolidayBaseAI):
    """A holiday invasion: while it lasts, whenever this district has no invasion one starts (Halloween: skelecogs)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('HolidaySuitInvasionManagerAI')
    CHECK_EVERY = 60.0
    NUM_SUITS = 1000

    def __init__(self, air, holidayId):
        HolidayBaseAI.HolidayBaseAI.__init__(self, air, holidayId)
        self.taskName = 'holidayInvasion-%d' % holidayId

    def start(self):
        self.__check(None)
        taskMgr.doMethodLater(self.CHECK_EVERY, self.__check, self.taskName)

    def stop(self):
        taskMgr.remove(self.taskName)

    def __check(self, task):
        mgr = getattr(self.air, 'suitInvasionManager', None)
        if mgr is not None and not mgr.getInvading():
            skeleton = self.holidayId in (ToontownGlobals.HALLOWEEN, ToontownGlobals.SKELECOG_INVASION)
            mgr.startInvasion(random.choice(SuitDNA.suitHeadTypes), self.NUM_SUITS, skeleton)
        if task is not None:
            return task.again


class CogTakeoverEventAI(HolidayBaseAI.HolidayBaseAI):
    """The Cogs take over every town building for DURATION seconds. Idle toon buildings on the streets become Cog buildings (busy ones are
    retried each minute), and a building the toons win back during the event is taken again. When it ends, the buildings the event took
    are given back to the toons (busy ones are retried every 30 s for up to 10 minutes). Cog buildings that were there before stay."""
    notify = DirectNotifyGlobal.directNotify.newCategory('CogTakeoverEventAI')
    DURATION = 90 * 60.0
    CHECK_EVERY = 60.0
    GIVE_BACK_EVERY = 30.0
    GIVE_BACK_FOR = 10 * 60.0

    def __init__(self, air, holidayId):
        HolidayBaseAI.HolidayBaseAI.__init__(self, air, holidayId)
        self.taskName = 'cogTakeoverEvent-%d' % holidayId
        self.endTaskName = self.taskName + '-end'
        self.giveBackTaskName = self.taskName + '-giveBack'
        self.taken = set()               # (zoneId, block) the event turned into Cog buildings
        self.startedAt = time.time()
        self.floors = 0                  # floors cleared by toons while the event runs
        self.buildingsTaken = 0
        self.buildingsCleared = 0
        self.byToon = {}                 # avId -> [name, floors, buildings]
        self.byStreet = {}               # street zone -> floors
        self.hood = int(getattr(air, 'takeoverHood', 0) or 0)     # the playground's zone id (2000 Toontown Central...), 0 for every town

    @staticmethod
    def running(air):
        """The runner of the event in this district, or None."""
        manager = getattr(air, 'holidayManager', None)
        if manager is None:
            return None
        return manager.currentHolidays.get(ToontownGlobals.COG_TAKEOVER_EVENT)

    def __toonName(self, avId):
        toon = self.air.doId2do.get(avId)
        return toon.getName() if toon is not None and hasattr(toon, 'getName') else 'toon %s' % avId

    HOOD_NAMES = {0: 'every playground', 1000: "Donald's Dock", 2000: 'Toontown Central', 3000: 'The Brrrgh', 4000: "Minnie's Melodyland", 5000: "Daisy's Gardens", 9000: 'Dreamland'}

    def inHood(self, zoneId):
        """Is this street zone in the playground the event is running in?"""
        return not self.hood or (zoneId - zoneId % 1000) == self.hood

    def hoodName(self):
        return self.HOOD_NAMES.get(self.hood, 'zone %d' % self.hood)

    def floorCleared(self, toonIds, streetZone):
        """A floor of a Cog building was won by these toons (called by the building's interior)."""
        if not self.inHood(streetZone):
            return
        self.floors += 1
        self.byStreet[streetZone] = self.byStreet.get(streetZone, 0) + 1
        for avId in toonIds:
            if avId:
                entry = self.byToon.setdefault(avId, [self.__toonName(avId), 0, 0])
                entry[1] += 1
        self.__save()

    def buildingCleared(self, victorIds, streetZone=0):
        """A whole Cog building was won back by these toons."""
        if streetZone and not self.inHood(streetZone):
            return
        self.buildingsCleared += 1
        for avId in victorIds:
            if avId:
                entry = self.byToon.setdefault(avId, [self.__toonName(avId), 0, 0])
                entry[2] += 1
        self.__save()

    def summary(self):
        top = self.standings()[:5]
        text = self.hoodName() + ': %d floors cleared, %d buildings taken, %d buildings won back, %d toons took part.' % (self.floors, self.buildingsTaken, self.buildingsCleared, len(self.byToon))
        if top:
            text += ' Top: ' + ', '.join('%d. %s %d floors (%d beans)' % (place, name, floors, prize) for avId, name, floors, buildings, place, prize in top)
        return text

    # prizes in jelly beans, by place (floors cleared; toons with the same floors share a place). [last place, beans]: the first row that fits wins.
    # Everyone else with at least MIN_FLOORS floors gets PARTICIPATION. gameconfig.json can change them: {"cog_takeover_prizes": [[1, 5000], [2, 3000]]}
    def shortSummary(self):
        """A few short lines that fit in a phone's message box."""
        lines = [self.hoodName(), 'Floors: %d' % self.floors, 'Taken: %d  Won back: %d' % (self.buildingsTaken, self.buildingsCleared)]
        for avId, name, floors, buildings, place, prize in self.standings()[:3]:
            lines.append('%d. %s - %d' % (place, name[:14], floors))
        return '\n'.join(lines)

    PRIZES = [[1, 5000], [2, 3000], [3, 2000], [10, 1000]]
    PARTICIPATION = 250
    MIN_FLOORS = 3

    def prizeTable(self):
        configured = GameConfig.get('cog_takeover_prizes', None)
        try:
            if configured:
                return sorted([[int(r), int(b)] for r, b in configured])
        except Exception:
            self.notify.warning('cog_takeover_prizes in gameconfig.json is not a list of [place, beans] pairs; using the default prizes')
        return [list(p) for p in self.PRIZES]

    def standings(self):
        """[(avId, name, floors, buildings, place, prize)], best first."""
        table = self.prizeTable()
        rows = sorted(((a, e[0], e[1], e[2]) for a, e in self.byToon.items()), key=lambda r: (-r[2], -r[3]))
        out = []
        for avId, name, floors, buildings in rows:
            place = 1 + sum(1 for r in rows if r[2] > floors)
            prize = 0
            if floors >= 1 and (place <= 3 or floors >= self.MIN_FLOORS):
                for last, beans in table:
                    if place <= last:
                        prize = beans
                        break
                else:
                    if floors >= self.MIN_FLOORS:
                        prize = self.PARTICIPATION
            out.append((avId, name, floors, buildings, place, prize))
        return out

    def __payPrizes(self):
        """Give each toon their prize: a toon playing now gets it in their pocket (the rest overflows to the bank) with a message; one who has
        left gets it added to their bank in the database."""
        if getattr(self, 'paid', False):
            return
        self.paid = True
        standings = self.standings()
        told = set()
        for avId, name, floors, buildings, place, prize in standings:
            text = self.resultText(floors, place, prize)
            toon = self.air.doId2do.get(avId)
            try:
                if toon is not None and hasattr(toon, 'addMoney'):
                    if prize > 0:
                        toon.addMoney(prize)
                    toon.d_setSystemMessage(0, text)
                    told.add(avId)
                    self.notify.info('prize: %s (%d) place %d, %d floors, %d beans (playing)' % (name, avId, place, floors, prize))
                else:
                    if prize > 0:
                        self.__payOffline(avId, name, place, floors, prize)
                    self.queueMessage(avId, text)
            except Exception:
                self.notify.warning('could not pay %s (%s): %s' % (name, avId, traceback.format_exc()))
        # everyone else who is playing hears how it ended
        winner = ('Winner: %s\n%d floors' % (standings[0][1][:16], standings[0][2])) if standings else 'No floors cleared'
        for toon in list(self.air.doId2do.values()):
            try:
                if toon.doId not in told and hasattr(toon, 'addMoney') and hasattr(toon, 'd_setSystemMessage') and toon.isPlayerControlled():
                    toon.d_setSystemMessage(0, 'Takeover over!\n%s' % winner)
            except Exception:
                pass

    @staticmethod
    def ordinal(n):
        return '%d%s' % (n, 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th'))

    @classmethod
    def resultText(cls, floors, place, prize):
        # short: the message box on a phone only has room for about four short lines
        text = 'Takeover: %s place!\n%d floors' % (cls.ordinal(place), floors)
        if prize > 0:
            text += '\n+%d beans!' % prize
        return text

    PENDING_FILE = '/ot/data/cog_takeover_messages.json'

    @classmethod
    def queueMessage(cls, avId, text):
        """Keep a message for a toon who has left, to show when they next play (any district)."""
        try:
            try:
                with open(cls.PENDING_FILE) as f:
                    pending = json.load(f)
            except Exception:
                pending = {}
            pending[str(avId)] = text
            with open(cls.PENDING_FILE, 'w') as f:
                json.dump(pending, f)
        except Exception:
            pass

    @classmethod
    def deliverMessage(cls, toon):
        """Show a toon the message kept for them, if any (called a few seconds after they arrive)."""
        try:
            with open(cls.PENDING_FILE) as f:
                pending = json.load(f)
            text = pending.pop(str(toon.doId), None)
            if text is None:
                return
            with open(cls.PENDING_FILE, 'w') as f:
                json.dump(pending, f)
            toon.d_setSystemMessage(0, text)
        except Exception:
            pass

    def __payOffline(self, avId, name, place, floors, prize):
        dclass = self.air.dclassesByName['DistributedToonAI']

        def got(dc, fields):
            try:
                if dc != dclass or not fields:
                    return
                bank = fields.get('setBankMoney', (0,))[0]
                limit = fields.get('setMaxBankMoney', (12000,))[0]
                amount = max(0, min(bank + prize, limit))
                self.air.dbInterface.updateObject(self.air.dbId, avId, dclass, {'setBankMoney': (amount,)})
                self.notify.info('prize: %s (%d) place %d, %d floors, %d beans (offline, bank now %d)' % (name, avId, place, floors, prize, amount))
            except Exception:
                self.notify.warning('could not pay offline toon %s: %s' % (avId, traceback.format_exc()))
        self.air.dbInterface.queryObject(self.air.dbId, avId, got)

    @staticmethod
    def stateFile(air):
        district = ''.join(c if c.isalnum() else '_' for c in (getattr(air, 'districtName', '') or 'district'))
        return '/ot/data/cog_takeover_%s.json' % district

    @classmethod
    def pendingState(cls, air):
        """The saved state of an event this district was running when it stopped (a restart), or None. The holiday manager turns the event
        back on for it, so the buildings it took are not left Cog buildings for good and the prizes are still paid."""
        try:
            with open(cls.stateFile(air)) as f:
                data = json.load(f)
            return data if data.get('active') else None
        except Exception:
            return None

    def __file(self):
        return self.stateFile(self.air)

    def __load(self, data):
        self.startedAt = data.get('started', self.startedAt)
        self.hood = int(data.get('hood', self.hood) or 0)
        self.endsAt = data.get('endsAt', self.endsAt)
        self.floors = data.get('floors', 0)
        self.buildingsTaken = data.get('buildingsTaken', 0)
        self.buildingsCleared = data.get('buildingsCleared', 0)
        self.byToon = {int(a): [e['name'], e['floors'], e['buildings']] for a, e in data.get('byToon', {}).items()}
        self.byStreet = {int(z): n for z, n in data.get('byStreet', {}).items()}
        self.taken = {(int(z), int(b)) for z, b in data.get('taken', [])}
        self.paid = bool(data.get('paid', False))

    def __save(self):
        try:
            data = {'active': getattr(self, 'active', True), 'endsAt': getattr(self, 'endsAt', 0), 'taken': [list(t) for t in self.taken],
                    'started': self.startedAt, 'hood': self.hood, 'floors': self.floors, 'buildingsTaken': self.buildingsTaken, 'buildingsCleared': self.buildingsCleared,
                    'byToon': {str(a): {'name': e[0], 'floors': e[1], 'buildings': e[2]} for a, e in self.byToon.items()}, 'byStreet': {str(z): n for z, n in self.byStreet.items()},
                    'paid': getattr(self, 'paid', False), 'standings': [{'avId': r[0], 'name': r[1], 'floors': r[2], 'place': r[4], 'prize': r[5]} for r in self.standings()]}
            with open(self.__file(), 'w') as f:
                json.dump(data, f)
        except Exception:
            self.notify.warning('could not save the takeover stats: ' + traceback.format_exc())

    def __planners(self):
        for zoneId, sp in list(self.air.suitPlanners.items()):
            if getattr(sp, 'buildingMgr', None) and zoneId < 10000 and self.inHood(zoneId):
                yield zoneId, sp

    def start(self):
        self.active = True
        try:
            duration = float(GameConfig.get('cog_takeover_minutes', self.DURATION / 60)) * 60.0       # gameconfig.json can shorten it for a test
        except Exception:
            duration = self.DURATION
        self.endsAt = time.time() + duration
        saved = self.pendingState(self.air)
        if saved is not None:
            self.__load(saved)
            self.notify.info('Cog takeover event resumed after a restart: %s' % self.summary())
        for zoneId, sp in self.__planners():
            sp.takeoverEvent = True
        remaining = self.endsAt - time.time()
        if remaining <= 0:
            self.notify.info('Cog takeover event ran out while the server was down; ending it.')
            taskMgr.doMethodLater(5.0, self.__timeUp, self.endTaskName)
            return
        self.notify.info('Cog takeover event started (%d minutes left).' % (remaining / 60))
        self.__save()
        self.__takeOver(None)
        taskMgr.doMethodLater(self.CHECK_EVERY, self.__takeOver, self.taskName)
        taskMgr.doMethodLater(remaining, self.__timeUp, self.endTaskName)

    def stop(self):
        taskMgr.remove(self.taskName)
        taskMgr.remove(self.endTaskName)
        self.__save()
        self.notify.info('Cog takeover event over; giving %d buildings back. %s' % (len(self.taken), self.summary()))
        self.air.writeServerEvent('cogTakeoverEnd', 0, self.summary())
        self.__payPrizes()
        self.__save()
        self.__giveBack(None, time.time() + self.GIVE_BACK_FOR)

    def __timeUp(self, task):
        manager = getattr(self.air, 'holidayManager', None)
        if manager is not None:
            manager.forceHoliday(self.holidayId, False)
            manager.update()
        return task.done

    def __takeOver(self, task):
        count = 0
        for zoneId, sp in self.__planners():
            sp.takeoverEvent = True
            hoodInfo = sp.SuitHoodInfo[sp.hoodInfoIdx]
            levels = hoodInfo[sp.SUIT_HOOD_INFO_LVL]
            for building in sp.buildingMgr.getBuildings():
                try:
                    if not hasattr(building, 'suitTakeOver') or not hasattr(building, 'fsm'):
                        continue
                    if building.fsm.getCurrentState().getName() != 'toon':
                        continue
                    height = random.randint(0, 4)
                    try:
                        level = sp.chooseSuitLevel(levels, height)
                    except Exception:
                        level = random.choice(levels)
                    sp.suitTakeOver(building.block, random.choice(SuitDNA.suitDepts), level - 1, height)
                    self.buildingsTaken += 1
                    self.taken.add((zoneId, building.block))
                    count += 1
                except Exception:
                    self.notify.warning('could not take over block %s in %s: %s' % (getattr(building, 'block', type(building).__name__), zoneId, traceback.format_exc()))
        if count:
            self.notify.info('Cog takeover: %d more buildings taken (%d in all).' % (count, len(self.taken)))
            self.__save()
        if task is not None:
            return task.again

    def __giveBack(self, task, deadline=None):
        if deadline is not None:
            self.deadline = deadline
        left = set()
        for zoneId, block in list(self.taken):
            sp = self.air.suitPlanners.get(zoneId)
            if sp is None or not getattr(sp, 'buildingMgr', None):
                continue
            try:
                building = sp.buildingMgr.getBuilding(block)
                state = building.fsm.getCurrentState().getName()
                if state != 'suit':
                    if state in ('becomingSuit', 'clearOutToonInterior'):
                        left.add((zoneId, block))
                    continue
                elevator = getattr(building, 'elevator', None)
                if hasattr(building, 'interior') or elevator is None or elevator.fsm.getCurrentState().getName() != 'waitEmpty':
                    left.add((zoneId, block))
                    continue
                building.b_setVictorList([0, 0, 0, 0])
                building.updateSavedBy([])
                sp.trimming = True
                try:
                    building.toonTakeOver()
                finally:
                    sp.trimming = False
            except Exception:
                self.notify.warning('could not give back block %s in %s: %s' % (block, zoneId, traceback.format_exc()))
        self.taken = left
        self.__save()
        if left and time.time() < self.deadline:
            taskMgr.remove(self.giveBackTaskName)
            taskMgr.doMethodLater(self.GIVE_BACK_EVERY, self.__giveBack, self.giveBackTaskName)
            return
        if left:
            self.notify.info('%d event buildings left to the normal trim.' % len(left))
        for zoneId, sp in self.__planners():
            sp.takeoverEvent = False
        self.active = False
        self.__save()
        if task is not None:
            return task.done


class AprilFoolsManagerAI(HolidayBaseAI.HolidayBaseAI):
    """April Toons: the clients do the rest (low gravity at estates, silly doodles, the April Toons SpeedChat menu); this tells
    toons already at an estate to switch their gravity when the holiday starts or ends."""

    def __send(self, field):
        estateMgr = getattr(self.air, 'estateMgr', None)
        if estateMgr is not None:
            estateMgr.sendUpdate(field, [])

    def start(self):
        self.__send('startAprilFools')

    def stop(self):
        self.__send('stopAprilFools')
