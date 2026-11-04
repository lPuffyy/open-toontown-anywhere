"""Which server object runs each party activity (the activities are ported from the original game). The Valentine's and winter
versions are the same games under their own class names, which is what makes clients show their holiday look."""
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyCannonActivityAI import DistributedPartyCannonActivityAI
from toontown.parties.DistributedPartyCatchActivityAI import DistributedPartyCatchActivityAI
from toontown.parties.DistributedPartyCogActivityAI import DistributedPartyCogActivityAI
from toontown.parties.DistributedPartyDance20ActivityAI import DistributedPartyDance20ActivityAI
from toontown.parties.DistributedPartyDanceActivityAI import DistributedPartyDanceActivityAI
from toontown.parties.DistributedPartyFireworksActivityAI import DistributedPartyFireworksActivityAI
from toontown.parties.DistributedPartyJukebox40ActivityAI import DistributedPartyJukebox40ActivityAI
from toontown.parties.DistributedPartyJukeboxActivityAI import DistributedPartyJukeboxActivityAI
from toontown.parties.DistributedPartyTrampolineActivityAI import DistributedPartyTrampolineActivityAI
from toontown.parties.DistributedPartyTugOfWarActivityAI import DistributedPartyTugOfWarActivityAI
from toontown.parties.DistributedPartyVictoryTrampolineActivityAI import DistributedPartyVictoryTrampolineActivityAI
from toontown.parties.DistributedPartyValentineDanceActivityAI import DistributedPartyValentineDanceActivityAI
from toontown.parties.DistributedPartyValentineDance20ActivityAI import DistributedPartyValentineDance20ActivityAI
from toontown.parties.DistributedPartyValentineJukeboxActivityAI import DistributedPartyValentineJukeboxActivityAI
from toontown.parties.DistributedPartyValentineJukebox40ActivityAI import DistributedPartyValentineJukebox40ActivityAI
from toontown.parties.DistributedPartyValentineTrampolineActivityAI import DistributedPartyValentineTrampolineActivityAI
from toontown.parties.DistributedPartyWinterCatchActivityAI import DistributedPartyWinterCatchActivityAI
from toontown.parties.DistributedPartyWinterCogActivityAI import DistributedPartyWinterCogActivityAI
from toontown.parties.DistributedPartyWinterTrampolineActivityAI import DistributedPartyWinterTrampolineActivityAI

A = PartyGlobals.ActivityIds
ACTIVITY_CLASSES = {A.PartyJukebox: DistributedPartyJukeboxActivityAI,
                    A.PartyCannon: DistributedPartyCannonActivityAI,
                    A.PartyTrampoline: DistributedPartyTrampolineActivityAI,
                    A.PartyVictoryTrampoline: DistributedPartyVictoryTrampolineActivityAI,
                    A.PartyCatch: DistributedPartyCatchActivityAI,
                    A.PartyDance: DistributedPartyDanceActivityAI,
                    A.PartyTugOfWar: DistributedPartyTugOfWarActivityAI,
                    A.PartyFireworks: DistributedPartyFireworksActivityAI,
                    A.PartyJukebox40: DistributedPartyJukebox40ActivityAI,
                    A.PartyDance20: DistributedPartyDance20ActivityAI,
                    A.PartyCog: DistributedPartyCogActivityAI,
                    A.PartyValentineDance: DistributedPartyValentineDanceActivityAI,
                    A.PartyValentineDance20: DistributedPartyValentineDance20ActivityAI,
                    A.PartyValentineJukebox: DistributedPartyValentineJukeboxActivityAI,
                    A.PartyValentineJukebox40: DistributedPartyValentineJukebox40ActivityAI,
                    A.PartyValentineTrampoline: DistributedPartyValentineTrampolineActivityAI,
                    A.PartyWinterCatch: DistributedPartyWinterCatchActivityAI,
                    A.PartyWinterCog: DistributedPartyWinterCogActivityAI,
                    A.PartyWinterTrampoline: DistributedPartyWinterTrampolineActivityAI}
