from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.estate import BankGlobals


class DistributedBankAI(DistributedFurnitureItemAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBankAI')

    def __init__(self, air, furnitureMgr, catalogItem):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, catalogItem)
        self.busyAvId = 0

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId, globalClockDelta.getRealNetworkTime(bits=16)])

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.busyAvId:
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return
        if avId != self.furnitureMgr.house.ownerId:
            self.d_setMovie(BankGlobals.BANK_MOVIE_NOT_OWNER, avId)
            return
        self.busyAvId = avId
        self.d_setMovie(BankGlobals.BANK_MOVIE_GUI, avId)

    def transferMoney(self, amount):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if avId != self.busyAvId or av is None:
            return
        mode = BankGlobals.BANK_MOVIE_NO_OP
        if amount > 0:                                   # deposit: jar -> bank
            amount = min(amount, av.getMoney(), av.getMaxBankMoney() - av.getBankMoney())
            if amount > 0:
                av.b_setMoney(av.getMoney() - amount)
                av.b_setBankMoney(av.getBankMoney() + amount)
                mode = BankGlobals.BANK_MOVIE_DEPOSIT
        elif amount < 0:                                 # withdraw: bank -> jar
            amount = min(-amount, av.getBankMoney(), av.getMaxMoney() - av.getMoney())
            if amount > 0:
                av.b_setBankMoney(av.getBankMoney() - amount)
                av.b_setMoney(av.getMoney() + amount)
                mode = BankGlobals.BANK_MOVIE_WITHDRAW
        self.d_setMovie(mode, avId)
        self.busyAvId = 0
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
        self.d_setMovie(BankGlobals.BANK_MOVIE_CLEAR, 0)
