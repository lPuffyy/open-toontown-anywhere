"""Codes players type on the Options page of the Shticker Book ("Codes" tab) for a gift.

The person running the server writes the codes in /ot/data/codes.json (looked at again on every try, so a new code works at once):
  {"WELCOME": {"beans": 500},
   "SNOWDAY": {"items": [{"type": "Clothing", "args": [1821, 0]}, {"type": "Emote", "args": [5]}],
               "start": "2026-12-01", "end": "2027-01-03", "max": 200, "per": "toon"}}
  beans  jellybeans for the toon's pocket (what does not fit goes to the bank)
  items  catalog items for the toon's mailbox: "type" names a catalog item class (Clothing, Furniture, Emote, Chat, Nametag,
         Wallpaper, Flooring, Moulding, Wainscoting, Window, Bean, Accessory, Garden, Pole, Rental, PetTrick, AnimatedFurniture,
         ToonStatue, GardenStarter) and "args" is what that class takes, as in the catalog
  start, end  the days the code works (server time, both included; leave out for always)
  max    how many times it can be used in all (leave out for no limit)
  per    "account" (default: once for each player account) or "toon" (once for each toon)
  active false turns a code off without deleting it
Codes are not case sensitive. Who used which code is kept in /ot/data/code_redemptions.json.

The client sends its code to the code redemption global object; every district listens on that channel and the one the toon is
in answers (the others ignore it)."""
import contextlib
import datetime
import importlib
import json
import os
import re
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalAI import DistributedObjectGlobalAI
from toontown.toonbase import ToontownGlobals

try:
    import fcntl
except ImportError:          # (Windows, when testing outside the server)
    fcntl = None

CODES_FILE = '/ot/data/codes.json'
USED_FILE = '/ot/data/code_redemptions.json'
LOCK_FILE = '/ot/data/code_redemptions.lock'

# the results the Options page knows (TTCodeRedemptionConsts.RedeemErrors), and the award results it shows for result 4
SUCCESS, INVALID, EXPIRED, AWARD_FAILED, TOO_MANY_TRIES, UNAVAILABLE = 0, 1, 2, 4, 5, 6
AWARD_UNKNOWN, AWARD_MAILBOX_FULL, AWARD_ALREADY_RECEIVED = 1, 3, 12
BAD_TRIES = 5                 # wrong codes allowed ...
BAD_TRIES_WINDOW = 600.0      # ... in this many seconds, before the toon has to wait


def normalize(code):
    return re.sub(r'[\s-]', '', str(code)).upper()


@contextlib.contextmanager
def usedTransaction():
    """with usedTransaction() as used: ... -- the record of who used which code, with no other district in between."""
    os.makedirs(os.path.dirname(USED_FILE), exist_ok=True)
    with open(LOCK_FILE, 'a') as lock:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            try:
                with open(USED_FILE) as f:
                    used = json.load(f)
            except (OSError, ValueError):
                used = {}
            yield used
            tmp = USED_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(used, f)
            os.replace(tmp, USED_FILE)
        finally:
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_UN)


def readCodes():
    with open(CODES_FILE) as f:
        data = json.load(f)
    return {normalize(k): v for k, v in data.items() if isinstance(v, dict)} if isinstance(data, dict) else {}


def makeItem(spec):
    """A catalog item from {"type": "Clothing", "args": [1821, 0]}."""
    kind = str(spec.get('type', ''))
    if not re.match(r'^[A-Za-z]+$', kind):
        raise ValueError('bad item type %r' % kind)
    name = 'Catalog%sItem' % kind
    module = importlib.import_module('toontown.catalog.' + name)
    return getattr(module, name)(*spec.get('args', []))


def inDates(info, today):
    def day(key):
        value = info.get(key)
        return datetime.datetime.strptime(value, '%Y-%m-%d').date() if value else None
    start, end = day('start'), day('end')
    return (start is None or today >= start) and (end is None or today <= end)


class TTCodeRedemptionMgrAI(DistributedObjectGlobalAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('TTCodeRedemptionMgrAI')

    def __init__(self, air):
        DistributedObjectGlobalAI.__init__(self, air)
        self.badTries = {}        # avId -> times of their recent wrong codes

    def redeemCode(self, context, code):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not hasattr(av, 'mailboxContents'):
            return                # the toon is in another district, which answers
        result, awardResult = self.__redeem(av, normalize(code)[:64])
        self.sendUpdateToAvatarId(avId, 'redeemCodeResult', [context, result, awardResult])

    def __redeem(self, av, code):
        now = time.time()
        tries = [t for t in self.badTries.get(av.doId, []) if now - t < BAD_TRIES_WINDOW]
        self.badTries[av.doId] = tries
        if len(tries) >= BAD_TRIES:
            return TOO_MANY_TRIES, 0
        try:
            codes = readCodes()
        except FileNotFoundError:
            codes = {}
        except (OSError, ValueError):
            self.notify.warning('could not read %s' % CODES_FILE)
            return UNAVAILABLE, 0
        info = codes.get(code)
        if not code or info is None:
            tries.append(now)
            return INVALID, 0
        if info.get('active', True) is False or not inDates(info, datetime.date.today()):
            return EXPIRED, 0
        try:
            items = [makeItem(spec) for spec in info.get('items', [])]
            beans = int(info.get('beans', 0))
        except Exception:
            self.notify.warning('code %s has a bad gift: %s' % (code, info))
            return AWARD_FAILED, AWARD_UNKNOWN
        if len(av.mailboxContents) + len(items) > ToontownGlobals.MaxMailboxContents:
            return AWARD_FAILED, AWARD_MAILBOX_FULL
        who = str(av.doId) if info.get('per', 'account') == 'toon' else 'account:%s' % getattr(av, 'DISLid', av.doId)
        with usedTransaction() as used:
            record = used.setdefault(code, {'count': 0, 'by': []})
            if who in record['by']:
                return AWARD_FAILED, AWARD_ALREADY_RECEIVED
            if info.get('max') is not None and record['count'] >= int(info['max']):
                return EXPIRED, 0
            record['count'] += 1
            record['by'].append(who)
        if beans > 0:
            av.addMoney(beans)
        if items:
            av.b_setMailboxContents(av.mailboxContents + items)
            av.b_setCatalogNotify(av.catalogNotify, ToontownGlobals.NewItems)
        self.air.writeServerEvent('code-redeemed', av.doId, '%s|%s beans|%d items' % (code, beans, len(items)))
        self.notify.info('%s used code %s (%s beans, %d items)' % (av.doId, code, beans, len(items)))
        return SUCCESS, 0
