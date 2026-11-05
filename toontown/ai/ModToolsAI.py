"""The district's side of the moderator panel (served by docker/auth_service.py at /mod/, outside the game).

Every few seconds each district writes the toons playing in it to <dir>/online-<district>.json, and carries out the
panel's commands, which arrive as files in <dir>/cmd/: send a toon a message, log it out, or change it (beans, laff,
name, a gift in its mailbox...). A command for one playing toon is done by the district that toon is in, which writes
<dir>/done/<id>.json; a command for everyone (avId 0) is done by every district. Reading a toon, or changing one that is
not playing, is marked anyDistrict: the first district to claim the file does it, through the database. The panel
removes old command files.
"""
import json
import os
import time
import traceback

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import ConfigVariableString

from toontown.hood import ZoneUtil
from toontown.toonbase import ToontownGlobals, TTLocalizer


class ModToolsAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('ModToolsAI')
    WRITE_EVERY = 5.0
    POLL_EVERY = 1.5
    MAX_AGE = 60.0                  # older commands are ignored (a district that just started does not replay them)
    BOOT_KICK = 151                 # "You have been logged out by an administrator working on the servers."

    def __init__(self, air):
        self.air = air
        self.dir = ConfigVariableString('mod-tools-dir', '/ot/data/mod').getValue()
        self.cmdDir = os.path.join(self.dir, 'cmd')
        self.doneDir = os.path.join(self.dir, 'done')
        self.seen = {}              # command file -> when it was handled here
        self.since = {}             # avId -> when this district first saw it
        try:
            os.makedirs(self.cmdDir, exist_ok=True)
            os.makedirs(self.doneDir, exist_ok=True)
        except OSError:
            self.notify.warning('cannot use %s: the moderator panel will not see this district' % self.dir)
            return
        taskMgr.doMethodLater(self.WRITE_EVERY, self.__write, 'modToolsWrite')
        taskMgr.doMethodLater(self.POLL_EVERY, self.__poll, 'modToolsPoll')
        taskMgr.doMethodLater(20.0, lambda task: self.writeItemList(), 'modToolsItems')

    def __toons(self):
        return [do for do in list(self.air.doId2do.values())
                if hasattr(do, 'friendsList') and hasattr(do, 'isPlayerControlled') and do.isPlayerControlled()]

    def describeZone(self, zoneId):
        """Where a zone is, in words: 'Toontown Central, Silly Street', 'Estate of Flippy', ..."""
        try:
            if zoneId >= ToontownGlobals.DynamicZonesBegin:
                estateMgr = getattr(self.air, 'estateMgr', None)
                ownerId = estateMgr.getOwnerFromZone(zoneId) if estateMgr else None
                if ownerId:
                    owner = self.air.doId2do.get(ownerId)
                    name = owner.getName() if owner else 'toon %s' % ownerId
                    inside = zoneId != estateMgr.getEstateZones(ownerId)[0] if estateMgr.getEstateZones(ownerId) else False
                    return ('Inside the house, estate of %s' if inside else 'Estate of %s') % name
                return 'Party, minigame, race or other private area'
            hoodId = ZoneUtil.getCanonicalHoodId(zoneId)
            hood = ToontownGlobals.hoodNameMap.get(hoodId, 'Zone %s' % hoodId)
            if isinstance(hood, (tuple, list)):
                hood = hood[-1]
            canonical = ZoneUtil.getCanonicalZoneId(zoneId)
            where = ZoneUtil.getWhereName(canonical, True)
            branch = canonical - canonical % 100
            street = TTLocalizer.GlobalStreetNames.get(branch, (None, None, None))[2] if canonical % 1000 >= 100 else None
            parts = [hood]
            if street and where not in ('playground',):
                parts.append(street)
            if where in ('toonInterior', 'suitInterior'):
                title = TTLocalizer.zone2TitleDict.get(canonical, ('a building', ''))[0] or 'a building'
                parts.append('inside ' + title)
            elif where not in ('playground', 'street') and len(parts) == 1:
                parts.append({'cogHQExterior': 'courtyard', 'cogHQLobby': 'lobby', 'factoryExterior': 'factory grounds',
                              'factoryInterior': 'factory', 'mintInterior': 'mint', 'stageInterior': 'DA office',
                              'countryClubInterior': 'golf course'}.get(where, where))
            return ', '.join(parts)
        except Exception:
            return 'Zone %s' % zoneId

    def __write(self, task):
        try:
            now = time.time()
            toons = []
            here = set()
            for toon in self.__toons():
                here.add(toon.doId)
                self.since.setdefault(toon.doId, now)
                zoneId = toon.zoneId or 0
                toons.append({'avId': toon.doId, 'name': toon.getName(), 'zone': zoneId, 'where': self.describeZone(zoneId),
                              'hp': getattr(toon, 'hp', 0), 'maxHp': getattr(toon, 'maxHp', 0),
                              'battle': getattr(toon, 'battleId', -1) >= 0, 'access': toon.getAccessLevel(),
                              'since': int(self.since[toon.doId])})
            for avId in [a for a in self.since if a not in here]:
                del self.since[avId]
            data = {'updated': int(now), 'district': self.air.districtName, 'toons': toons}
            path = os.path.join(self.dir, 'online-%s.json' % self.air.districtName.replace('/', '_'))
            with open(path + '.tmp', 'w') as f:
                json.dump(data, f)
            os.replace(path + '.tmp', path)
        except Exception:
            self.notify.warning('could not write the online list: %s' % traceback.format_exc())
        return task.again

    def __poll(self, task):
        try:
            now = time.time()
            for name in sorted(os.listdir(self.cmdDir)):
                if not name.endswith('.json') or name in self.seen:
                    continue
                path = os.path.join(self.cmdDir, name)
                try:
                    cmd = json.load(open(path))
                except (OSError, ValueError):
                    continue                     # still being written, or already removed
                if now - cmd.get('time', 0) > self.MAX_AGE:
                    self.seen[name] = now
                    continue
                avId = int(cmd.get('avId', 0))
                if cmd.get('anyDistrict'):
                    # reading a toon, or changing one that is not playing: the first district to claim the file does it
                    try:
                        os.rename(path, path[:-5] + '.claimed')
                    except OSError:
                        continue                 # another district took it
                    self.seen[name] = now
                    self.__doFromDatabase(cmd, avId, lambda result, ok=True, name=name: self.__finish(name, result, ok))
                elif avId:
                    toon = self.air.doId2do.get(avId)
                    if toon is None or not hasattr(toon, 'isPlayerControlled') or not toon.isPlayerControlled():
                        continue                 # not in this district: another one will do it
                    self.seen[name] = now
                    try:
                        result, ok = self.__do(cmd, toon), True
                    except ModError as e:
                        result, ok = str(e), False
                    self.__finish(name, result, ok)
                else:
                    self.seen[name] = now
                    count = sum(1 for toon in self.__toons() if self.__do(cmd, toon))
                    self.notify.info('moderator panel: %s to everyone here (%d toons)' % (cmd.get('action'), count))
            for name in [n for n, t in self.seen.items() if now - t > self.MAX_AGE * 2]:
                del self.seen[name]
        except Exception:
            self.notify.warning('could not read the panel commands: %s' % traceback.format_exc())
        return task.again

    def __finish(self, name, result, ok=True):
        try:
            with open(os.path.join(self.doneDir, name), 'w') as f:
                json.dump({'ok': ok, 'district': self.air.districtName, 'result': result, 'time': int(time.time())}, f)
        except Exception:
            self.notify.warning('could not write a panel result: %s' % traceback.format_exc())

    def __do(self, cmd, toon):
        action = cmd.get('action')
        text = str(cmd.get('text', ''))[:300]
        self.notify.info('moderator panel (%s): %s toon %s %s %s' % (cmd.get('by', '?'), action, toon.doId, text, cmd.get('op', '')))
        if action == 'message':
            toon.d_setSystemMessage(0, text)
            return 'sent'
        if action in ('kick', 'ban'):
            if text:
                toon.d_setSystemMessage(0, text)
            self.air.eject(toon.GetPuppetConnectionChannel(toon.doId), self.BOOT_KICK, text or 'Logged out by a moderator.')
            return 'logged out'
        if action == 'edit':
            return self.__editLive(toon, cmd.get('op'), cmd.get('value'), bool(cmd.get('add')))
        return 'unknown action'

    # ---- reading and changing a toon -------------------------------------------------------------------------------
    def __editLive(self, toon, op, value, add):
        from toontown.catalog import CatalogItem, CatalogItemList
        name = toon.getName()
        if op == 'money':
            amount = clamp((toon.getMoney() if add else 0) + int(value), 0, toon.getMaxMoney())
            toon.b_setMoney(amount)
            return '%s now carries %d jelly beans' % (name, amount)
        if op == 'bank':
            amount = clamp((toon.getBankMoney() if add else 0) + int(value), 0, toon.getMaxBankMoney())
            toon.b_setBankMoney(amount)
            return '%s now has %d jelly beans in the bank' % (name, amount)
        if op == 'maxHp':
            maxHp = clamp(int(value), 15, ToontownGlobals.MaxHpLimit)
            toon.b_setMaxHp(maxHp)
            toon.toonUp(maxHp)
            return '%s now has %d max laff' % (name, maxHp)
        if op == 'heal':
            toon.toonUp(toon.getMaxHp())
            return '%s is at full laff' % name
        if op == 'name':
            newName = checkName(value)
            toon.b_setName(newName)
            return 'renamed to %s' % newName
        if op == 'pinkSlips':
            toon.b_setPinkSlips(clamp(int(value), 0, 255))
            return '%s has %d pink slips' % (name, clamp(int(value), 0, 255))
        if op == 'emotes':
            toon.b_setEmoteAccess([1] * len(toon.getEmoteAccess()))
            return 'unlocked every emote'
        if op == 'teleport':
            toon.b_setHoodsVisited(ToontownGlobals.HoodsForTeleportAll)
            toon.b_setTeleportAccess(ToontownGlobals.HoodsForTeleportAll)
            return 'can teleport everywhere'
        if op == 'gags':
            if value == 'empty':
                toon.inventory.zeroInv()
            else:
                toon.inventory.maxOutInv()
            toon.d_setInventory(toon.inventory.makeNetString())
            return 'gags emptied' if value == 'empty' else 'gags restocked'
        if op == 'cheesy':
            effect, minutes = [int(v) for v in (list(value) + [60])[:2]] if isinstance(value, list) else (int(value), 60)
            toon.b_setCheesyEffect(effect, 0, int(time.time() / 60) + max(1, minutes) if effect else 0)
            return 'cheesy effect %d for %d minutes' % (effect, minutes) if effect else 'cheesy effect removed'
        if op == 'maxtoon':
            from toontown.spellbook.MagicWordIndex import MaxToon
            return MaxToon.handleWord(MaxToon.__new__(MaxToon), None, toon.doId, toon)
        if op == 'gift':
            item = makeItem(str(value))
            checkGift(item, toon.dna.getGender())
            contents = CatalogItemList.CatalogItemList(toon.mailboxContents, store=CatalogItem.Customization)
            contents.append(item)
            toon.b_setMailboxContents(contents)
            toon.b_setCatalogNotify(toon.catalogNotify, ToontownGlobals.NewItems)
            return '%s is in the mailbox' % item.getName()
        raise ModError('Unknown change.')

    OFFLINE_ONLY_LIVE = ('gags', 'maxtoon')

    def __doFromDatabase(self, cmd, avId, done):
        """Read a toon from the database, then answer ('inspect') or change it ('edit', for a toon that is not playing)."""
        action, op = cmd.get('action'), cmd.get('op')
        if action == 'edit' and op in self.OFFLINE_ONLY_LIVE:
            return done('That can only be done while the toon is playing.', False)
        dclass = self.air.dclassesByName['DistributedToonAI']

        def got(dc, fields):
            try:
                if dc != dclass or not fields:
                    return done('No toon with that id.', False)
                if action == 'inspect':
                    return done(describeToon(avId, fields))
                updates, result = self.__editFields(fields, op, cmd.get('value'), bool(cmd.get('add')))
                self.notify.info('moderator panel (%s): edit offline toon %s %s %s' % (cmd.get('by', '?'), avId, op, list(updates)))
                self.air.dbInterface.updateObject(self.air.dbId, avId, dclass, updates)
                done(result)
            except ModError as e:
                done(str(e), False)
            except Exception:
                self.notify.warning('panel database job failed: %s' % traceback.format_exc())
                done('Something went wrong on the server.', False)
        try:
            self.air.dbInterface.queryObject(self.air.dbId, avId, got)
        except Exception:
            done('Could not reach the database.', False)

    def __editFields(self, fields, op, value, add):
        from toontown.catalog import CatalogItem, CatalogItemList
        get = lambda field, default=0: fields.get(field, (default,))[0]
        name = get('setName', '')
        if op == 'money':
            amount = clamp((get('setMoney') if add else 0) + int(value), 0, get('setMaxMoney', 40))
            return {'setMoney': (amount,)}, '%s now carries %d jelly beans' % (name, amount)
        if op == 'bank':
            amount = clamp((get('setBankMoney') if add else 0) + int(value), 0, get('setMaxBankMoney', 12000))
            return {'setBankMoney': (amount,)}, '%s now has %d jelly beans in the bank' % (name, amount)
        if op == 'maxHp':
            maxHp = clamp(int(value), 15, ToontownGlobals.MaxHpLimit)
            return {'setMaxHp': (maxHp,), 'setHp': (maxHp,)}, '%s now has %d max laff' % (name, maxHp)
        if op == 'heal':
            return {'setHp': (get('setMaxHp', 15),)}, '%s is at full laff' % name
        if op == 'name':
            newName = checkName(value)
            return {'setName': (newName,)}, 'renamed to %s' % newName
        if op == 'pinkSlips':
            return {'setPinkSlips': (clamp(int(value), 0, 255),)}, '%s has %d pink slips' % (name, clamp(int(value), 0, 255))
        if op == 'emotes':
            return {'setEmoteAccess': ([1] * len(get('setEmoteAccess', [0] * 20)),)}, 'unlocked every emote'
        if op == 'teleport':
            hoods = list(ToontownGlobals.HoodsForTeleportAll)
            return {'setHoodsVisited': (hoods,), 'setTeleportAccess': (hoods,)}, 'can teleport everywhere'
        if op == 'cheesy':
            effect, minutes = [int(v) for v in (list(value) + [60])[:2]] if isinstance(value, list) else (int(value), 60)
            expire = int(time.time() / 60) + max(1, minutes) if effect else 0
            return {'setCheesyEffect': (effect, 0, expire)}, 'cheesy effect %d for %d minutes' % (effect, minutes) if effect else 'cheesy effect removed'
        if op == 'gift':
            from toontown.toon import ToonDNA
            item = makeItem(str(value))
            dna = ToonDNA.ToonDNA()
            dna.makeFromNetString(get('setDNAString', b''))
            checkGift(item, dna.getGender())
            contents = CatalogItemList.CatalogItemList(get('setMailboxContents', b''), store=CatalogItem.Customization)
            contents.append(item)
            notify = fields.get('setCatalogNotify', (0, 0))
            return ({'setMailboxContents': (contents.getBlob(store=CatalogItem.Customization),),
                     'setCatalogNotify': (notify[0], ToontownGlobals.NewItems)}, '%s is in the mailbox' % item.getName())
        raise ModError('Unknown change.')

    def writeItemList(self):
        """Every item the panel can give, for its item picker (the same for every district)."""
        try:
            path = os.path.join(self.dir, 'items.json')
            items = listItems()
            with open(path + '.tmp', 'w') as f:
                json.dump(items, f)
            os.replace(path + '.tmp', path)
        except Exception:
            self.notify.warning('could not write the item list: %s' % traceback.format_exc())


class ModError(Exception):
    """A change the panel asked for that cannot be done; the message is shown in the panel."""


def clamp(value, low, high):
    return max(low, min(high, value))


def checkName(value):
    newName = ' '.join(str(value or '').split())
    if not 1 <= len(newName) <= 30:
        raise ModError('A name needs 1 to 30 letters.')
    return newName


# ---- items the panel can give, as codes like "furniture:1300" or "clothing:101:0" -----------------------------------
def makeItem(code):
    from toontown.catalog import (CatalogFurnitureItem, CatalogClothingItem, CatalogEmoteItem, CatalogAccessoryItem,
                                  CatalogWindowItem, CatalogWallpaperItem, CatalogFlooringItem, CatalogMouldingItem,
                                  CatalogWainscotingItem, CatalogPoleItem, CatalogNametagItem, CatalogPetTrickItem,
                                  CatalogGardenItem, CatalogBeanItem, CatalogChatItem)
    parts = code.split(':')
    try:
        kind, args = parts[0], [int(p) for p in parts[1:]]
        make = {'furniture': CatalogFurnitureItem.CatalogFurnitureItem, 'clothing': CatalogClothingItem.CatalogClothingItem,
                'emote': CatalogEmoteItem.CatalogEmoteItem, 'accessory': CatalogAccessoryItem.CatalogAccessoryItem,
                'window': CatalogWindowItem.CatalogWindowItem, 'wallpaper': CatalogWallpaperItem.CatalogWallpaperItem,
                'flooring': CatalogFlooringItem.CatalogFlooringItem, 'moulding': CatalogMouldingItem.CatalogMouldingItem,
                'wainscoting': CatalogWainscotingItem.CatalogWainscotingItem, 'pole': CatalogPoleItem.CatalogPoleItem,
                'nametag': CatalogNametagItem.CatalogNametagItem, 'pettrick': CatalogPetTrickItem.CatalogPetTrickItem,
                'garden': CatalogGardenItem.CatalogGardenItem, 'beans': CatalogBeanItem.CatalogBeanItem,
                'chat': CatalogChatItem.CatalogChatItem}[kind]
        if kind == 'beans' and not 1 <= args[0] <= 9999:
            raise ModError('Give 1 to 9999 jelly beans.')
        return make(*args)
    except ModError:
        raise
    except Exception:
        raise ModError('Unknown item %s.' % code)


BOYS_ONLY = (0, 3)          # CatalogClothingItem articles: ABoysShirt, ABoysShorts
GIRLS_ONLY = (1, 4, 5)      # AGirlsShirt, AGirlsShorts, AGirlsSkirt


def clothingArticle(item):
    from toontown.catalog import CatalogClothingItem
    if not hasattr(item, 'clothingType'):
        return None
    return CatalogClothingItem.ClothingTypes.get(item.clothingType, (None,))[0]


def checkGift(item, gender):
    article = clothingArticle(item)
    if article in BOYS_ONLY and gender == 'f' or article in GIRLS_ONLY and gender == 'm':
        raise ModError("That clothing doesn't fit this toon.")


def listItems():
    from toontown.catalog import (CatalogFurnitureItem, CatalogClothingItem, CatalogAccessoryItemGlobals, CatalogWindowItem,
                                  CatalogWallpaperItem, CatalogFlooringItem, CatalogMouldingItem, CatalogWainscotingItem)
    from toontown.fishing import FishGlobals
    from toontown.pets import PetTricks
    from toontown.estate import GardenGlobals
    from otp.otpbase import OTPLocalizer
    items = []
    seen = {}

    def add(kind, label, code):
        try:
            item = makeItem(code)
            name = item.getName()
            if not name:
                return
            count = seen.get((kind, name), 0) + 1          # several shirts share one name: number them instead of hiding them
            seen[(kind, name)] = count
            if count > 1:
                name = '%s #%d' % (name, count)
            extra = ''
            if kind == 'Clothing':
                article = clothingArticle(item)
                extra = ' (boy)' if article in BOYS_ONLY else ' (girl)' if article in GIRLS_ONLY else ''
            items.append({'code': code, 'kind': kind, 'name': name + extra})
        except Exception:
            pass
    for t in sorted(CatalogFurnitureItem.FurnitureTypes):
        add('Furniture', '', 'furniture:%d' % t)
    for t in sorted(CatalogClothingItem.ClothingTypes):
        add('Clothing', '', 'clothing:%d:0' % t)
    for t in sorted(CatalogAccessoryItemGlobals.AccessoryTypes):
        add('Accessory', '', 'accessory:%d' % t)
    for i in range(len(OTPLocalizer.EmoteList)):
        add('Emote', '', 'emote:%d' % i)
    for t in sorted(CatalogWindowItem.WindowViewTypes):
        add('Window view', '', 'window:%d' % t)
    for t in sorted(CatalogWallpaperItem.WallpaperTypes):
        add('Wallpaper', '', 'wallpaper:%d:0' % t)
    for t in sorted(CatalogFlooringItem.FlooringTypes):
        add('Flooring', '', 'flooring:%d:0' % t)
    for t in sorted(CatalogMouldingItem.MouldingTypes):
        add('Moulding', '', 'moulding:%d:0' % t)
    for t in sorted(CatalogWainscotingItem.WainscotingTypes):
        add('Wainscoting', '', 'wainscoting:%d:0' % t)
    for r in range(FishGlobals.MaxRodId + 1):
        add('Fishing rod', '', 'pole:%d' % r)
    for s in range(len(TTLocalizer.NametagFontNames)):
        add('Nametag', '', 'nametag:%d' % s)
    for t in sorted(PetTricks.TrickId2scIds):
        add('Doodle trick', '', 'pettrick:%d' % t)
    for g in sorted(GardenGlobals.Specials):
        add('Garden', '', 'garden:%d:3' % g)
    return items


DEPTS = ('Bossbot', 'Lawbot', 'Cashbot', 'Sellbot')


def describeToon(avId, fields):
    """What the panel shows about a toon, from its database fields."""
    from toontown.toon import ToonDNA
    from toontown.toon.Experience import Experience
    from toontown.toonbase import ToontownBattleGlobals
    from toontown.catalog import CatalogItem, CatalogItemList
    get = lambda field, default=0: fields.get(field, (default,))[0]
    out = {'avId': avId, 'name': get('setName', ''), 'hp': get('setHp', 15), 'maxHp': get('setMaxHp', 15),
           'money': get('setMoney'), 'maxMoney': get('setMaxMoney', 40), 'bank': get('setBankMoney'), 'maxBank': get('setMaxBankMoney', 12000),
           'maxCarry': get('setMaxCarry', 20), 'pinkSlips': get('setPinkSlips'), 'access': get('setAccessLevel'),
           'lastHood': ToontownGlobals.hoodNameMap.get(get('setLastHood'), ''), 'friends': [f[0] for f in get('setFriendsList', [])]}
    if isinstance(out['lastHood'], (tuple, list)):
        out['lastHood'] = out['lastHood'][-1]
    try:
        dna = ToonDNA.ToonDNA()
        dna.makeFromNetString(get('setDNAString', b''))
        out['species'] = TTLocalizer.AnimalToSpecies.get(dna.getAnimal(), dna.getAnimal())
        out['gender'] = 'boy' if dna.getGender() == 'm' else 'girl'
    except Exception:
        out['species'], out['gender'] = '', ''
    try:
        exp = Experience(get('setExperience', b''))
        access = list(get('setTrackAccess', [0] * 7))
        out['tracks'] = [{'name': ToontownBattleGlobals.Tracks[i].title(), 'has': bool(access[i]) if i < len(access) else False,
                          'exp': exp.getExp(i), 'level': exp.getExpLevel(i) + 1} for i in range(len(ToontownBattleGlobals.Tracks))]
    except Exception:
        out['tracks'] = []
    quests = list(get('setQuests', []))
    out['quests'] = len(quests) // 5
    out['questTier'] = fields.get('setRewardHistory', (0, []))[0]
    levels, types, merits = (list(fields.get(f, ([0] * 4,))[0]) for f in ('setCogLevels', 'setCogTypes', 'setCogMerits'))
    parts = list(get('setCogParts', [0] * 4))
    out['cogSuits'] = [{'dept': DEPTS[i], 'level': levels[i] + 1, 'type': types[i] + 1, 'merits': merits[i] if i < len(merits) else 0,
                        'hasSuit': bool(parts[i]) if i < len(parts) else False} for i in range(4)]
    out['fish'] = len(fields.get('setFishCollection', ([],))[0])
    out['flowers'] = len(fields.get('setFlowerCollection', ([],))[0])
    emotes = list(get('setEmoteAccess', []))
    out['emotes'] = '%d of %d' % (sum(1 for e in emotes if e), len(emotes))
    out['sos'] = len(get('setNPCFriendsDict', []))
    out['teleport'] = len(get('setTeleportAccess', []))
    cheesy = fields.get('setCheesyEffect', (0, 0, 0))
    out['cheesy'] = cheesy[0] if cheesy[2] * 60 > time.time() else 0
    for field, key, store in (('setMailboxContents', 'mailbox', CatalogItem.Customization),
                              ('setDeliverySchedule', 'onOrder', CatalogItem.Customization | CatalogItem.DeliveryDate)):
        try:
            out[key] = [item.getName() for item in CatalogItemList.CatalogItemList(get(field, b''), store=store)]
        except Exception:
            out[key] = []
    return out
