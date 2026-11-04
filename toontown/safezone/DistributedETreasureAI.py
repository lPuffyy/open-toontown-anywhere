from . import DistributedSZTreasureAI


class DistributedETreasureAI(DistributedSZTreasureAI.DistributedSZTreasureAI):
    """A treasure on the ground of an estate."""

    def __init__(self, air, treasurePlanner, x, y, z):
        DistributedSZTreasureAI.DistributedSZTreasureAI.__init__(self, air, treasurePlanner, x, y, z)
