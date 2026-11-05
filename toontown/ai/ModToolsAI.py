"""The district's side of the moderator panel (served by docker/auth_service.py at /mod/, outside the game).

Every few seconds each district writes the toons playing in it to <dir>/online-<district>.json, and carries out the
panel's commands, which arrive as files in <dir>/cmd/: send a toon a message, or log a toon out. A command for one toon is done by the district that toon is in, which writes <dir>/done/<id>.json; a command
for everyone (avId 0) is done by every district. The panel removes old command files.
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
                if avId:
                    toon = self.air.doId2do.get(avId)
                    if toon is None or not hasattr(toon, 'isPlayerControlled') or not toon.isPlayerControlled():
                        continue                 # not in this district: another one will do it
                    self.seen[name] = now
                    result = self.__do(cmd, toon)
                    with open(os.path.join(self.doneDir, name), 'w') as f:
                        json.dump({'ok': True, 'district': self.air.districtName, 'result': result, 'time': int(now)}, f)
                else:
                    self.seen[name] = now
                    count = sum(1 for toon in self.__toons() if self.__do(cmd, toon))
                    self.notify.info('moderator panel: %s to everyone here (%d toons)' % (cmd.get('action'), count))
            for name in [n for n, t in self.seen.items() if now - t > self.MAX_AGE * 2]:
                del self.seen[name]
        except Exception:
            self.notify.warning('could not read the panel commands: %s' % traceback.format_exc())
        return task.again

    def __do(self, cmd, toon):
        action = cmd.get('action')
        text = str(cmd.get('text', ''))[:300]
        self.notify.info('moderator panel (%s): %s toon %s %s' % (cmd.get('by', '?'), action, toon.doId, text))
        if action == 'message':
            toon.d_setSystemMessage(0, text)
            return 'sent'
        if action in ('kick', 'ban'):
            if text:
                toon.d_setSystemMessage(0, text)
            self.air.eject(toon.GetPuppetConnectionChannel(toon.doId), self.BOOT_KICK, text or 'Logged out by a moderator.')
            return 'logged out'
        return 'unknown action'
