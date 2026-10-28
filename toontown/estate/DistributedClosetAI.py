from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.estate import ClosetGlobals
from toontown.toon import ToonDNA


class DistributedClosetAI(DistributedFurnitureItemAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedClosetAI')

    def __init__(self, air, furnitureMgr, catalogItem):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, catalogItem)
        self.customerId = 0

    def getOwnerId(self):
        return self.furnitureMgr.house.ownerId

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId, globalClockDelta.getRealNetworkTime(bits=16)])

    def __state(self, mode, av):
        tops = list(av.getClothesTopsList()) if av else []
        bots = list(av.getClothesBottomsList()) if av else []
        gender = av.dna.gender if av else 'm'
        self.sendUpdate('setState', [mode, self.customerId, self.getOwnerId(), gender, tops, bots])

    def enterAvatar(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        if self.customerId:
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return
        self.customerId = avId
        self.__state(ClosetGlobals.OPEN, av)
        taskMgr.doMethodLater(ClosetGlobals.TIMEOUT_TIME, self.__timeout, self.uniqueName('timeout'))

    def __timeout(self, task):
        avId = self.customerId
        if avId:
            self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_TIMEOUT, avId)
        self.__finish()

    def __finish(self):
        taskMgr.remove(self.uniqueName('timeout'))
        self.customerId = 0
        self.sendUpdate('setState', [ClosetGlobals.CLOSED, 0, self.getOwnerId(), 'm', [], []])

    def delete(self):
        taskMgr.remove(self.uniqueName('timeout'))
        DistributedFurnitureItemAI.delete(self)

    def setDNA(self, blob, finished, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.customerId:
            return
        if finished == 0:                         # live preview for everyone watching
            self.sendUpdate('setCustomerDNA', [avId, blob])
            return
        if finished == 2 and avId == self.getOwnerId():
            self.__commit(av, blob, which)
        self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_COMPLETE, avId)
        self.__finish()
        self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_CLEAR, 0)

    def __commit(self, av, blob, which):
        new = ToonDNA.ToonDNA()
        new.makeFromNetString(blob)
        cur = av.dna
        if which & ClosetGlobals.SHIRT:
            want = (new.topTex, new.topTexColor, new.sleeveTex, new.sleeveTexColor)
            tops = list(av.getClothesTopsList())
            for i in range(0, len(tops), 4):
                if tuple(tops[i:i + 4]) == want:
                    tops[i:i + 4] = [cur.topTex, cur.topTexColor, cur.sleeveTex, cur.sleeveTexColor]
                    cur.topTex, cur.topTexColor, cur.sleeveTex, cur.sleeveTexColor = want
                    av.b_setClothesTopsList(tops)
                    break
        if which & ClosetGlobals.SHORTS:
            want = (new.botTex, new.botTexColor)
            bots = list(av.getClothesBottomsList())
            for i in range(0, len(bots), 2):
                if tuple(bots[i:i + 2]) == want:
                    bots[i:i + 2] = [cur.botTex, cur.botTexColor]
                    cur.botTex, cur.botTexColor = want
                    av.b_setClothesBottomsList(bots)
                    break
        av.b_setDNAString(cur.makeNetString())

    def removeItem(self, item, topOrBottom):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.customerId or avId != self.getOwnerId():
            return
        item = list(item)
        if topOrBottom == 0:
            lst = list(av.getClothesTopsList())
            n = 4
        else:
            lst = list(av.getClothesBottomsList())
            n = 2
        for i in range(0, len(lst), n):
            if lst[i:i + n] == item:
                del lst[i:i + n]
                if topOrBottom == 0:
                    av.b_setClothesTopsList(lst)
                else:
                    av.b_setClothesBottomsList(lst)
                break
        self.__state(ClosetGlobals.OPEN, av)
