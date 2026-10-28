import math
from panda3d.core import Point3
from toontown.toonbase import ToontownGlobals
InputTimeout = 15
TireMovieTimeout = 120
MinWall = (-20.0, -15.0)
MaxWall = (20.0, 15.0)
TireRadius = 1.5
WallMargin = 1 + TireRadius
StartingPositions = (Point3(MinWall[0] + WallMargin, MinWall[1] + WallMargin, TireRadius),
 Point3(MaxWall[0] - WallMargin, MaxWall[1] - WallMargin, TireRadius),
 Point3(MinWall[0] + WallMargin, MaxWall[1] - WallMargin, TireRadius),
 Point3(MaxWall[0] - WallMargin, MinWall[1] + WallMargin, TireRadius))
NumMatches = 3
NumRounds = 2
PointsDeadCenter = {0: 5,
 1: 5,
 2: 5,
 3: 4,
 4: 3}
PointsInCorner = 1
FarthestLength = math.sqrt((MaxWall[0] - TireRadius) * (MaxWall[0] - TireRadius) + (MaxWall[1] - TireRadius) * (MaxWall[1] - TireRadius))
BonusPointsForPlace = (3,
 2,
 1,
 0)
ExpandFeetPerSec = 5
ScoreCountUpRate = 0.15
ShowScoresDuration = 4.0
NumTreasures = {ToontownGlobals.ToontownCentral: 2,
 ToontownGlobals.DockHarbor: 2,
 ToontownGlobals.GardenGrove: 2,
 ToontownGlobals.MelodyMeadow: 2,
 ToontownGlobals.TheBrrrgh: 1,
 ToontownGlobals.SlumberSprings: 1}
NumPenalties = {ToontownGlobals.ToontownCentral: 0,
 ToontownGlobals.DockHarbor: 1,
 ToontownGlobals.GardenGrove: 1,
 ToontownGlobals.MelodyMeadow: 1,
 ToontownGlobals.TheBrrrgh: 2,
 ToontownGlobals.SlumberSprings: 2}
Obstacles = {ToontownGlobals.ToontownCentral: (),
 ToontownGlobals.DockHarbor: ((0, 0),),
 ToontownGlobals.GardenGrove: ((MinWall[0] / 2, 0), (MaxWall[0] / 2, 0)),
 ToontownGlobals.MelodyMeadow: ((0, MinWall[1] / 2), (0, MaxWall[1] / 2)),
 ToontownGlobals.TheBrrrgh: ((MinWall[0] / 2, 0),
                             (MaxWall[0] / 2, 0),
                             (0, MinWall[1] / 2),
                             (0, MaxWall[1] / 2)),
 ToontownGlobals.SlumberSprings: ((MinWall[0] / 2, MinWall[1] / 2),
                                    (MinWall[0] / 2, MaxWall[1] / 2),
                                    (MaxWall[0] / 2, MinWall[1] / 2),
                                    (MaxWall[0] / 2, MaxWall[1] / 2))}
ObstacleShapes = {ToontownGlobals.ToontownCentral: True,
 ToontownGlobals.DockHarbor: True,
 ToontownGlobals.GardenGrove: True,
 ToontownGlobals.MelodyMeadow: True,
 ToontownGlobals.TheBrrrgh: False,
 ToontownGlobals.SlumberSprings: False}
