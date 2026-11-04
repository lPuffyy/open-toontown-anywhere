from . import DistributedSZTreasureAI


class DistributedEFlyingTreasureAI(DistributedSZTreasureAI.DistributedSZTreasureAI):
    """A treasure floating over an estate while its cannons are rented: only a toon shot from a cannon can reach it."""

    def __init__(self, air, treasurePlanner, x, y, z):
        DistributedSZTreasureAI.DistributedSZTreasureAI.__init__(self, air, treasurePlanner, x, y, z)
