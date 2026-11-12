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

MIN_SIZE = 2
MAX_SIZE = 8

# what a request answers with
OP_POST = 1          # groupPost
OP_JOIN = 2          # groupJoin
OP_CLOSED = 3        # the group you were in has ended (or you were removed)
OP_LEAVE = 4         # groupLeave / groupDisband

OK = 0
BAD = 1              # not a valid request
BUSY = 2             # asked again too soon
FULL = 3             # the group is full, or there are too many groups
GONE = 4             # no such group (any more)
OWN = 5              # you cannot join your own group

# limits and timing (seconds)
MAX_GROUPS = 200
LIST_LIMIT = 60      # groups sent in one list
POST_COOLDOWN = 8.0
LIST_COOLDOWN = 1.0
JOIN_COOLDOWN = 1.5
MOVE_COOLDOWN = 3.0
HEARTBEAT = 15.0     # how often the host's client reports where it is
STALE = 120.0        # a group whose host has not reported for this long is removed
SWEEP_EVERY = 20.0
