from direct.directnotify import DirectNotifyGlobal
from toontown.estate.DistributedClosetAI import DistributedClosetAI
from toontown.estate import ClosetGlobals
from toontown.toon import ToonDNA

NONE = (0, 0, 0)


class DistributedTrunkAI(DistributedClosetAI):
    """The accessories trunk: like the closet, but for hats, glasses, backpacks and shoes. The trunk shows what the toon wears plus the
    toon's list for each kind; choosing one from the list swaps it with the one worn (so the old one goes back in the trunk)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrunkAI')

    # which (ToonDNA bit) -> (get the worn one, wear one, get the list, set the list)
    KINDS = {ToonDNA.HAT: ('getHat', 'b_setHat', 'getHatList', 'b_setHatList'),
             ToonDNA.GLASSES: ('getGlasses', 'b_setGlasses', 'getGlassesList', 'b_setGlassesList'),
             ToonDNA.BACKPACK: ('getBackpack', 'b_setBackpack', 'getBackpackList', 'b_setBackpackList'),
             ToonDNA.SHOES: ('getShoes', 'b_setShoes', 'getShoesList', 'b_setShoesList')}
    ORDER = (ToonDNA.HAT, ToonDNA.GLASSES, ToonDNA.BACKPACK, ToonDNA.SHOES)

    def _state(self, mode, av):
        lists = [list(getattr(av, self.KINDS[k][2])()) if av else [] for k in self.ORDER]
        gender = av.dna.gender if av else 'm'
        self.sendUpdate('setState', [mode, self.customerId, self.getOwnerId(), gender] + lists)

    def _finish(self):
        taskMgr.remove(self.uniqueName('timeout'))
        self.customerId = 0
        self.sendUpdate('setState', [ClosetGlobals.CLOSED, 0, self.getOwnerId(), 'm', [], [], [], []])

    def setDNA(self, *args):
        """hat, glasses, backpack, shoes (3 numbers each), finished (0 preview, 1 cancel, 2 done), which (ToonDNA bits)."""
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.customerId or len(args) != 14:
            return
        chosen = {k: tuple(args[i * 3:i * 3 + 3]) for i, k in enumerate(self.ORDER)}
        finished, which = args[12], args[13]
        if finished == 0:                         # live preview for everyone watching
            self.sendUpdate('setCustomerDNA', [avId] + list(args[:12]) + [which])
            return
        if finished == 2 and avId == self.getOwnerId():
            for kind in self.ORDER:
                if which & kind:
                    self.__wear(av, kind, chosen[kind])
        self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_COMPLETE, avId)
        self._finish()
        self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_CLEAR, 0)

    def __wear(self, av, kind, want):
        getWorn, wear, getList, setList = self.KINDS[kind]
        cur = tuple(getattr(av, getWorn)())
        if want == cur:
            return
        items = list(getattr(av, getList)())
        for i in range(0, len(items), 3):
            if tuple(items[i:i + 3]) == want:
                items[i:i + 3] = list(cur)            # what was worn goes back in the trunk (even "nothing", so it can be chosen again)
                getattr(av, setList)(items)
                getattr(av, wear)(*want)
                return
        self.notify.warning('%s chose an accessory they do not own: %s %s' % (av.doId, kind, want))

    def removeItem(self, idx, texture, color, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.customerId or avId != self.getOwnerId() or which not in self.KINDS:
            return
        getWorn, wear, getList, setList = self.KINDS[which]
        item = (idx, texture, color)
        items = list(getattr(av, getList)())
        for i in range(0, len(items), 3):
            if tuple(items[i:i + 3]) == item:
                del items[i:i + 3]
                getattr(av, setList)(items)
                break
        else:
            if tuple(getattr(av, getWorn)()) == item and item != NONE:
                getattr(av, wear)(*NONE)            # threw away the one being worn
        self._state(ClosetGlobals.OPEN, av)
