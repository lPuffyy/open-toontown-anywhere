import random
import traceback
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.fishing import BingoGlobals
from toontown.fishing import NormalBingo, FourCornerBingo, DiagonalBingo, ThreewayBingo, BlockoutBingo

CARD_CLASSES = {BingoGlobals.NORMAL_CARD: NormalBingo.NormalBingo,
                BingoGlobals.FOURCORNER_CARD: FourCornerBingo.FourCornerBingo,
                BingoGlobals.DIAGONAL_CARD: DiagonalBingo.DiagonalBingo,
                BingoGlobals.THREEWAY_CARD: ThreewayBingo.ThreewayBingo,
                BingoGlobals.BLOCKOUT_CARD: BlockoutBingo.BlockoutBingo}
# how often each kind of card comes up
CARD_WEIGHTS = ((BingoGlobals.NORMAL_CARD, 55), (BingoGlobals.FOURCORNER_CARD, 15), (BingoGlobals.DIAGONAL_CARD, 15),
                (BingoGlobals.THREEWAY_CARD, 10), (BingoGlobals.BLOCKOUT_CARD, 5))


class DistributedPondBingoManagerAI(DistributedObjectAI):
    """Fish bingo for one pond. Everyone fishing at the pond shares one card: each catch that fits a cell marks it for all of them,
    and when the card is full of lines the jackpot goes to everyone at the pond. The game only runs while someone is fishing.

    The client is a state machine that only accepts certain next states, so every toon on the pond has their own state tracked
    here and is walked through the states it needs."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPondBingoManagerAI')

    def __init__(self, air, pond):
        DistributedObjectAI.__init__(self, air)
        self.pond = pond
        self.members = {}              # avId -> the state that toon's client is in
        self.phase = 'Idle'            # Idle, WaitCountdown, Playing, Over
        self.cardId = 0
        self.typeId = BingoGlobals.NORMAL_CARD
        self.tileSeed = 0
        self.game = None
        self.gameState = 0
        self.phaseStamp = 0

    def __taskName(self):
        return 'bingoPhase-%d' % self.doId

    def getPondDoId(self):
        return self.pond.doId

    def closeForTheNight(self):
        """Bingo night is over: take everyone's game down gently, then go away."""
        taskMgr.remove(self.__taskName())
        self.phase = 'Closed'
        for avId in list(self.members):
            self.avatarExit(avId)
        taskMgr.doMethodLater(8.0, lambda task: (self.requestDelete() if not self.isDeleted() else None, task.done)[1], self.__taskName() + '-close')

    def delete(self):
        taskMgr.remove(self.__taskName())
        DistributedObjectAI.delete(self)

    # ---- who is playing ------------------------------------------------------------------------------------------------
    def avatarEnter(self, avId):
        if avId in self.members:
            return
        self.members[avId] = 'Off'
        self.__walk(avId, 'Intro')
        if self.phase == 'Playing':
            self.__walk(avId, 'WaitCountdown')
            self.sendUpdateToAvatarId(avId, 'setCardState', [self.cardId, self.typeId, self.tileSeed, self.gameState])
            self.__walk(avId, 'Playing', self.phaseStamp)
        else:
            self.__walk(avId, 'WaitCountdown')
            if self.phase == 'Idle':
                self.__startWaiting()

    def avatarExit(self, avId):
        if avId not in self.members:
            return
        route = self.__routeToOff(self.members[avId])
        if 'Playing' in route:        # the client builds its card when it enters Playing, so it must have been sent one
            self.sendUpdateToAvatarId(avId, 'setCardState', [self.cardId, self.typeId, self.tileSeed or 1, self.gameState or 1 << 12])
        for step in route:
            self.__walk(avId, step)
        del self.members[avId]
        if not self.members:
            taskMgr.remove(self.__taskName())
            self.phase = 'Idle'

    @staticmethod
    def __routeToOff(state):
        """The states a client must pass through to get from `state` to Off."""
        routes = {'Off': [], 'Intro': ['WaitCountdown', 'Playing', 'GameOver', 'Off'], 'WaitCountdown': ['Playing', 'GameOver', 'Off'],
                  'Playing': ['GameOver', 'Off'], 'Reward': ['Off'], 'GameOver': ['Off'], 'Intermission': ['Off']}
        return routes.get(state, [])

    def __walk(self, avId, state, stamp=None):
        if self.members.get(avId) == state:
            return
        if stamp is None:
            stamp = globalClockDelta.getRealNetworkTime(bits=16)
        self.members[avId] = state
        self.sendUpdateToAvatarId(avId, 'setState', [state, stamp])

    def __everyone(self, state, stamp=None):
        if stamp is None:
            stamp = globalClockDelta.getRealNetworkTime(bits=16)
        for avId in list(self.members):
            self.__walk(avId, state, stamp)

    # ---- the game cycle -------------------------------------------------------------------------------------------------
    def __later(self, seconds, method):
        taskMgr.remove(self.__taskName())
        taskMgr.doMethodLater(seconds, method, self.__taskName())

    def __startWaiting(self):
        self.phase = 'WaitCountdown'
        self.__everyone('WaitCountdown')
        self.__later(BingoGlobals.TIMEOUT_SESSION, self.__startGame)

    def __startGame(self, task=None):
        if not self.members:
            self.phase = 'Idle'
            return
        types, weights = zip(*CARD_WEIGHTS)
        self.cardId = (self.cardId + 1) % 65535
        self.typeId = random.choices(types, weights)[0]
        self.tileSeed = random.randint(1, 60000)
        self.game = CARD_CLASSES[self.typeId]()
        self.gameState = self.game.getGameState()
        try:
            self.game.generateCard(self.tileSeed, self.pond.getArea())
        except Exception:
            self.notify.warning('could not build the bingo card for pond %s: %s' % (self.pond.doId, traceback.format_exc()))
            self.game.cellList = []
        self.phase = 'Playing'
        self.phaseStamp = globalClockDelta.getRealNetworkTime(bits=16)
        for avId in list(self.members):
            self.sendUpdateToAvatarId(avId, 'setCardState', [self.cardId, self.typeId, self.tileSeed, self.gameState])
        self.__everyone('Playing', self.phaseStamp)
        self.__later(BingoGlobals.getGameTime(self.typeId), self.__timeUp)

    def __timeUp(self, task=None):
        self.phase = 'Over'
        self.__everyone('GameOver')
        self.__later(BingoGlobals.REWARD_TIMEOUT, self.__nextRound)

    def __nextRound(self, task=None):
        if not self.members:
            self.phase = 'Idle'
            return
        self.__startWaiting()

    # ---- messages from the clients ----------------------------------------------------------------------------------------
    def cardUpdate(self, cardId, cellId, genus, species):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.members or cardId != self.cardId or self.phase != 'Playing' or not 0 <= cellId < BingoGlobals.CARD_SIZE:
            return
        cells = self.game.cellList
        if cells and tuple(cells[cellId]) != (genus, species):
            self.notify.warning('%s sent a catch that does not fit cell %s' % (avId, cellId))
            return
        self.gameState |= 1 << cellId
        self.game.gameState = self.gameState
        self.sendUpdate('updateGameState', [self.gameState, cellId])

    def handleBingoCall(self, cardId):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.members or cardId != self.cardId or self.phase != 'Playing':
            return
        self.game.gameState = self.gameState
        try:
            won = bool(self.game.checkForBingo())
        except Exception:
            self.notify.warning('bingo check failed, trusting the call: %s' % traceback.format_exc())
            won = True
        if not won:
            return
        jackpot = BingoGlobals.getJackpot(self.typeId)
        for member in list(self.members):
            av = self.air.doId2do.get(member)
            if av is not None:
                av.addMoney(jackpot)
        self.phase = 'Over'
        self.__everyone('Reward')
        self.__later(BingoGlobals.REWARD_TIMEOUT, self.__nextRound)
