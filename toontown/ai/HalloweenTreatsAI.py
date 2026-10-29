import json
import os
import random
import time
import traceback

from direct.directnotify import DirectNotifyGlobal
from toontown.toonbase import GameConfig
from toontown.toonbase import ToontownGlobals


class HalloweenTreatsAI:
    """Our own simple Halloween fun, on while the Halloween holiday runs (the original's trick-or-treating and Black Cat tasks are not in the code):

      "Happy Halloween!" (Speed Chat)  a treat: a random Unite-style effect for that toon only (some laff, a gag restock or jellybeans),
                                       once every few minutes (gameconfig.json "treat_minutes", default 5)
      "Spooky!" (Speed Chat), by a cat   turns the toon into a Black Cat; say it again to turn back. A toon that is still black when the
                                       holiday is over is turned back the next time it arrives in a district.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('HalloweenTreatsAI')
    TREAT_PHRASE = 30251                 # "Happy Halloween!"
    CAT_PHRASE = 30252                   # "Spooky!"
    BLACK = 26                           # the color the game's own Black Cat uses (the DNA check lets it through)
    CATS_FILE = os.environ.get('OT_BLACK_CATS_FILE', '/ot/data/black_cats.json')

    def __init__(self, air):
        self.air = air
        self.lastTreat = {}              # avId -> when the toon last got a treat
        self.originals = None            # avId (as text) -> [head, arm, leg] colors before the toon turned black; read from the file when needed

    def active(self):
        return self.air.holidayManager.isHolidayRunning(ToontownGlobals.HALLOWEEN_PROPS)

    # ---- what the toon says
    def phraseSaid(self, toon, msgId):
        """Never raises: a bug here must not get in the way of chat."""
        try:
            if not self.active() or not toon.isPlayerControlled():
                return
            if msgId == self.TREAT_PHRASE:
                self.__treat(toon)
            elif msgId == self.CAT_PHRASE:
                self.__toggleBlackCat(toon)
        except Exception:
            self.notify.warning('Halloween phrase failed: ' + traceback.format_exc())

    def __treat(self, toon):
        from toontown.chat import ResistanceChat
        now = time.time()
        wait = GameConfig.get('treat_minutes', 5) * 60.0
        left = self.lastTreat.get(toon.doId, 0.0) + wait - now
        if left > 0:
            toon.d_setSystemMessage(0, 'Happy Halloween! Come back in %d minute(s) for another treat.' % (int(left // 60) + 1))
            return
        self.lastTreat[toon.doId] = now
        if len(self.lastTreat) > 1000:
            self.lastTreat = {a: t for a, t in self.lastTreat.items() if now - t < wait}
        textId = ResistanceChat.getRandomId()
        toon.doResistanceEffect(textId)
        toon.d_setSystemMessage(0, 'Trick or treat! You got: %s' % ResistanceChat.getItemText(textId))

    # ---- the Black Cat
    def __toggleBlackCat(self, toon):
        saved = self.__load()
        key = str(toon.doId)
        if key in saved:
            self.__setColors(toon, saved.pop(key))
            self.__save(saved)
            toon.d_setSystemMessage(0, 'You are your old self again.')
            return
        dna = toon.dna
        if dna.getAnimal() != 'cat' or (dna.headColor == dna.armColor == dna.legColor == self.BLACK):
            return
        saved[key] = [dna.headColor, dna.armColor, dna.legColor]
        self.__save(saved)
        self.__setColors(toon, [self.BLACK] * 3)
        toon.d_setSystemMessage(0, 'Spooky! You are a Black Cat. Say it again to turn back.')

    def toonArrived(self, toon):
        """A toon came into the district: after Halloween, turn a Black Cat back."""
        if self.active() or str(toon.doId) not in self.__load():
            return
        taskMgr.doMethodLater(3.0, self.__revert, 'blackCatRevert-%d' % toon.doId, extraArgs=[toon.doId])

    def __revert(self, avId):
        try:
            toon = self.air.doId2do.get(avId)
            saved = self.__load()
            if toon is None or str(avId) not in saved or self.active():
                return
            self.__setColors(toon, saved.pop(str(avId)))
            self.__save(saved)
            toon.d_setSystemMessage(0, 'Halloween is over: you are your old self again.')
        except Exception:
            self.notify.warning('could not turn a Black Cat back: ' + traceback.format_exc())

    def __setColors(self, toon, colors):
        head, arm, leg = colors
        toon.dna.headColor, toon.dna.armColor, toon.dna.legColor = head, arm, leg
        toon.b_setDNAString(toon.dna.makeNetString())

    def __load(self):
        if self.originals is None:
            try:
                with open(self.CATS_FILE) as f:
                    self.originals = json.load(f)
            except (OSError, ValueError):
                self.originals = {}
        return self.originals

    def __save(self, saved):
        self.originals = saved
        try:
            tmp = self.CATS_FILE + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(saved, f)
            os.replace(tmp, self.CATS_FILE)
        except OSError:
            self.notify.warning('could not save the Black Cat list: ' + traceback.format_exc())
