"""Shared by the UberDOG's group tracker (ToonGroupsUD.py) and the client's Groups page (toontown/shtiker/GroupsPage.py)."""

# group kinds: id -> (key, default size of the group)
KIND_SELLBOT_BOSS = 1
KIND_CASHBOT_BOSS = 2
KIND_LAWBOT_BOSS = 3
KIND_BOSSBOT_BOSS = 4
KIND_FACTORY = 5
KIND_MINT = 6
KIND_OFFICE = 7
KIND_GOLF = 8
KIND_BUILDING = 9
KIND_INVASION = 10
KIND_COGDO = 11
KIND_SELLBOT_BLDG = 12
KIND_CASHBOT_BLDG = 13
KIND_LAWBOT_BLDG = 14
KIND_BOSSBOT_BLDG = 15
KIND_FIELD_OFFICE = KIND_COGDO       # the Cogdominiums are the Sellbot Field Offices

KINDS = {
    KIND_SELLBOT_BOSS: 8,
    KIND_CASHBOT_BOSS: 8,
    KIND_LAWBOT_BOSS: 8,
    KIND_BOSSBOT_BOSS: 8,
    KIND_FACTORY: 4,
    KIND_MINT: 4,
    KIND_OFFICE: 4,
    KIND_GOLF: 4,
    KIND_BUILDING: 4,
    KIND_INVASION: 4,
    KIND_COGDO: 4,
    KIND_SELLBOT_BLDG: 4,
    KIND_CASHBOT_BLDG: 4,
    KIND_LAWBOT_BLDG: 4,
    KIND_BOSSBOT_BLDG: 4,
}
KIND_ORDER = [KIND_SELLBOT_BOSS, KIND_CASHBOT_BOSS, KIND_LAWBOT_BOSS, KIND_BOSSBOT_BOSS, KIND_FACTORY, KIND_MINT, KIND_OFFICE,
              KIND_GOLF, KIND_BUILDING, KIND_SELLBOT_BLDG, KIND_CASHBOT_BLDG, KIND_LAWBOT_BLDG, KIND_BOSSBOT_BLDG, KIND_INVASION, KIND_COGDO]

# ---- options of a group. They ride in the two numbers the messages already carry, so the message layout (the DC file) stays as it was:
#   kind byte:  bits 0-4 the kind, bits 5-7 the sub option (0 = any)
#   size byte:  bits 0-3 how many Toons, bit 4 friends only, bits 5-6 who it is for (LOOKING_*), bit 7 the activity has started
# sub options: kind -> number of choices after "Any" (their names are in the localizer, TTLocalizer.GroupSubNames)
SUBS = {
    KIND_FACTORY: 2,         # front entrance, side entrance
    KIND_MINT: 3,            # coin, dollar, bullion
    KIND_OFFICE: 4,          # offices A to D
    KIND_GOLF: 3,            # front three, middle six, back nine
    KIND_BUILDING: 5,        # 1 to 5 floors
    KIND_SELLBOT_BLDG: 5,
    KIND_CASHBOT_BLDG: 5,
    KIND_LAWBOT_BLDG: 5,
    KIND_BOSSBOT_BLDG: 5,
    KIND_INVASION: 4,        # which Cog department
    KIND_FIELD_OFFICE: 3,    # how it is run: beginner friendly, steady, speed run
    KIND_SELLBOT_BOSS: 2,    # first time, practice run
    KIND_CASHBOT_BOSS: 2,
    KIND_LAWBOT_BOSS: 2,
    KIND_BOSSBOT_BOSS: 2,
}
LOOKING_ANY = 0
LOOKING_BEGINNERS = 1
LOOKING_EXPERIENCED = 2
LOOKING_FAST = 3
LOOKING_COUNT = 4


def packKind(kind, sub=0):
    return (kind & 0x1F) | ((sub & 7) << 5)


def unpackKind(value):
    return value & 0x1F, (value >> 5) & 7


def packSize(size, friendsOnly=False, looking=0, started=False):
    return (size & 0x0F) | (0x10 if friendsOnly else 0) | ((looking & 3) << 5) | (0x80 if started else 0)


def isStarted(value):
    """Bit 7 of the size byte in a list: the group's host is inside its activity (a building, a factory, a boss fight...), so nobody
    can be taken to it."""
    return bool(value & 0x80)


def unpackSize(value):
    return value & 0x0F, bool(value & 0x10), (value >> 5) & 3

MIN_SIZE = 2
MAX_SIZE = 8

# what a request answers with
OP_POST = 1          # groupPost
OP_JOIN = 2          # groupJoin
OP_CLOSED = 3        # the group you were in has ended (or you were removed)
OP_LEAVE = 4         # groupLeave / groupDisband
OP_MEMBERS = 5       # someone joined or left the group you are in: ask for the list again

OK = 0
BAD = 1              # not a valid request
BUSY = 2             # asked again too soon
FULL = 3             # the group is full, or there are too many groups
GONE = 4             # no such group (any more)
OWN = 5              # you cannot join your own group
NOT_FRIEND = 6       # the group is for the host's friends only
STARTED = 7          # the group is inside its activity: nobody can join or be taken to it now

# limits and timing (seconds)
MAX_GROUPS = 200
LIST_LIMIT = 60      # groups sent in one list
POST_COOLDOWN = 8.0
LIST_COOLDOWN = 1.0
JOIN_COOLDOWN = 1.5
MOVE_COOLDOWN = 1.0
WATCH_EVERY = 1.5      # how often the host's client checks whether it has gone inside (or come out) and says so at once
HEARTBEAT = 15.0     # how often the host's client reports where it is
STALE = 120.0        # a group whose host has not reported for this long is removed
SWEEP_EVERY = 20.0
NAME_SEP = '\x1f'    # in a list entry the host's name is followed by the members' names, each after this
