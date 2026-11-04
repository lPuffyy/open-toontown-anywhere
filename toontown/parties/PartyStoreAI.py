"""Where planned parties live (in the original game the UberDOG kept them in a database).

One JSON file shared by every district (party_data/parties.json), read and written under a file lock, holds:
  parties:  partyId -> the party (host, times, activities, decorations, status, invitees, cost)
  invites:  avId -> [[inviteKey, partyId, status], ...]
  running:  hostId -> where the party is going on now (district, zone, guests, end time) so friends and party gates can find it
Times are the server's local time as strings ("%Y-%m-%d %H:%M:%S"), as the party planner sends them."""
import contextlib
import json
import os
import time

try:
    import fcntl
except ImportError:          # (Windows, when testing outside the server)
    fcntl = None

SAVE_DIR = 'party_data'
PATH = os.path.join(SAVE_DIR, 'parties.json')
LOCK = os.path.join(SAVE_DIR, 'parties.lock')
TIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def _empty():
    return {'nextPartyId': 1, 'nextInviteKey': 1, 'parties': {}, 'invites': {}, 'running': {}}


@contextlib.contextmanager
def transaction():
    """with transaction() as data: ... -- read, change and write back, with no other district in between."""
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(LOCK, 'a') as lock:
        if fcntl is not None:
            fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            data = read()
            yield data
            tmp = PATH + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(data, f)
            os.replace(tmp, PATH)
        finally:
            if fcntl is not None:
                fcntl.flock(lock, fcntl.LOCK_UN)


def read():
    try:
        with open(PATH) as f:
            data = json.load(f)
    except Exception:
        return _empty()
    for key, value in _empty().items():
        data.setdefault(key, value)
    return data


def partyTuple(partyId, party):
    """The party as the DC 'party' struct."""
    s = time.strptime(party['start'], TIME_FORMAT)
    e = time.strptime(party['end'], TIME_FORMAT)
    return (int(partyId), party['hostId'], s.tm_year, s.tm_mon, s.tm_mday, s.tm_hour, s.tm_min,
            e.tm_year, e.tm_mon, e.tm_mday, e.tm_hour, e.tm_min, party['isPrivate'], party['inviteTheme'],
            [tuple(a) for a in party['activities']], [tuple(d) for d in party['decors']], party['status'])


def toonView(data, avId):
    """Everything a toon's party fields should hold: (hosted parties, parties invited to, invites, replies to my parties)."""
    parties = data['parties']
    hosted = [partyTuple(pid, p) for pid, p in parties.items() if p['hostId'] == avId]
    invites = [tuple(i) for i in data['invites'].get(str(avId), []) if str(i[1]) in parties]
    invitedTo = [partyTuple(i[1], parties[str(i[1])]) for i in invites]
    replies = []
    for pid, p in parties.items():
        if p['hostId'] != avId:
            continue
        answers = []
        for inviteeId in p['invitees']:
            for key, partyId, status in data['invites'].get(str(inviteeId), []):
                if str(partyId) == pid:
                    answers.append((inviteeId, status))
        replies.append((int(pid), answers))
    return hosted, invitedTo, invites, replies
