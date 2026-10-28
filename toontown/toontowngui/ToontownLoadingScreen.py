from direct.gui.DirectGui import *
from panda3d.core import *
from toontown.toonbase import ToontownGlobals
from toontown.toonbase import TTLocalizer
import random

class ToontownLoadingScreen:

    def __init__(self):
        self.__expectedCount = 0
        self.__count = 0
        # the original backdrop is a picture with the Toontown Online logo in it: use our own sky, sized to the screen in begin()
        self.gui = NodePath('loadingGui')
        self.backdrop = None
        self.banner = loader.loadModel('phase_3/models/gui/toon_council').find('**/scroll')
        self.banner.reparentTo(self.gui)
        self.banner.setScale(0.58, 0.58, 0.58)
        self.banner.setPos(0, 0, 0.2)
        # the scroll's own size, measured before the tip label goes on it
        a, b = Point3(), Point3()
        self.banner.calcTightBounds(a, b, self.gui)
        self.scrollSize = (b.x - a.x, b.z - a.z)
        outline = (0.11, 0.25, 0.61, 1)
        # the tip, on the scroll: the sign font in brown, big enough to read on a phone
        self.tip = DirectLabel(guiId='ToontownLoadingScreenTip', parent=self.banner, relief=None, text='', text_scale=TTLocalizer.TLStip * 1.25, textMayChange=1, pos=(0, 0.0, 0.07), text_fg=(0.36, 0.22, 0.1, 1), text_wordwrap=11.5, text_align=TextNode.ACenter, text_font=ToontownGlobals.getSignFont())
        # the place name, centred over the bar: yellow with a blue edge, like the page's loading screen
        self.title = DirectLabel(guiId='ToontownLoadingScreenTitle', parent=self.gui, relief=None, pos=(0, 0, -0.69), text='', textMayChange=1, text_scale=0.115, text_fg=(1.0, 0.85, 0.15, 1), text_shadow=outline, text_align=TextNode.ACenter, text_font=ToontownGlobals.getSignFont())
        # a rounded-looking bar: dark glass track, yellow fill
        self.waitBar = DirectWaitBar(guiId='ToontownLoadingScreenWaitBar', parent=self.gui, frameSize=(-0.95, 0.95, -0.035, 0.035), pos=(0, 0, -0.84), text='', relief=DGG.FLAT, frameColor=(0.05, 0.15, 0.4, 0.55), barColor=(1.0, 0.85, 0.15, 1), borderWidth=(0.01, 0.01))
        return

    def destroy(self):
        self.tip.destroy()
        self.title.destroy()
        self.waitBar.destroy()
        self.banner.removeNode()
        if self.backdrop is not None:
            self.backdrop.removeNode()
        self.gui.removeNode()

    # Tips that do not fit this game as it runs on a phone and on our server are left out: keyboard keys that have no touch version, the
    # screenshot folder, resolution settings, things that are not in this build (true friends, invasions, holiday items, nearby-Doodle list)
    # and one that is no longer true (the house colour matching the Pick-A-Toon panel).
    SKIP_TIPS = ('F7', 'F8', 'F9', '"Home"', '"End"', 'Page Up', 'Tab key', 'Tab Key', 'Up Arrow', 'arrow keys', 'screen resolution',
                 'True Friends', 'Pick-A-Toon', 'nearby Doodles', 'Cog Invasion', 'holiday items', '"Control"', 'Ctrl', 'mouse')
    # replacements for the keyboard tips, with the touch controls
    TOUCH_TIPS = ('Tap the JUMP button to jump.',
                  'Tap the CAM button to change views of your Toon.',
                  'Open your Shticker Book with the book button in the corner of the screen.',
                  'Drag on the left side of the screen to move your Toon around.',
                  'Tap the chat buttons at the top of the screen to talk with SpeedChat or the keyboard.')

    def __tipsFor(self, tipCategory):
        tips = [t for t in TTLocalizer.TipDict.get(tipCategory) if not any(k in t for k in self.SKIP_TIPS)]
        if tipCategory == TTLocalizer.TIP_GENERAL:
            tips += list(self.TOUCH_TIPS)
        return tips or ['']

    def getTip(self, tipCategory):
        # (the sign font has no straight double-quote glyph: it draws an empty box)
        return TTLocalizer.TipTitle + '\n' + random.choice(self.__tipsFor(tipCategory)).replace('"', '')

    def __fitBackdrop(self):
        """A full-screen sky picture (2:1) scaled evenly to cover any screen shape."""
        if self.backdrop is not None:
            self.backdrop.removeNode()
        aspect = max(base.getAspectRatio(), 1.0)
        h = max(1.05, (aspect + 0.15) / 2.0)
        w = 2.0 * h
        cm = CardMaker('loading-backdrop')
        cm.setFrame(-w, w, -h, h)
        self.backdrop = self.gui.attachNewNode(cm.generate(), -10)
        tex = loader.loadTexture('phase_3/maps/pat_sky_backdrop.jpg')
        tex.setWrapU(SamplerState.WM_clamp)
        tex.setWrapV(SamplerState.WM_clamp)
        self.backdrop.setTexture(tex)
        self.backdrop.setDepthTest(False)
        self.backdrop.setDepthWrite(False)

    def begin(self, range, label, gui, tipCategory):
        self.__fitBackdrop()
        self.waitBar['range'] = range
        self.title['text'] = label
        self.tip['text'] = self.getTip(tipCategory)
        # fit the tip to the scroll: start big and shrink until the text fits inside it, then centre it (the label's origin is the first line)
        try:
            maxW, maxH = self.scrollSize[0] * 0.74, self.scrollSize[1] * 0.58
            sc = TTLocalizer.TLStip * 1.25
            wrapAbs = maxW / self.banner.getScale().x                  # the label lives in the scroll's scaled space
            for _step in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13):          # (`range` is a parameter name here)
                self.tip['text_scale'] = sc
                self.tip['text_wordwrap'] = wrapAbs / sc
                tn = self.tip.component('text0').textNode
                if tn.getHeight() * sc * self.banner.getScale().x <= maxH:
                    break
                sc *= 0.93
            self.tip.setZ(tn.getHeight() * sc / 2.0 - 0.35 * sc - 0.49)
        except Exception:
            import traceback
            print('loading screen tip fit failed', traceback.format_exc())
        self.__count = 0
        self.__expectedCount = range
        if gui:
            self.waitBar.reparentTo(self.gui)
            self.title.reparentTo(self.gui)
            self.gui.reparentTo(aspect2dp, DGG.NO_FADE_SORT_INDEX)
        else:
            self.waitBar.reparentTo(aspect2dp, DGG.NO_FADE_SORT_INDEX)
            self.title.reparentTo(aspect2dp, DGG.NO_FADE_SORT_INDEX)
            self.gui.reparentTo(hidden)
        self.waitBar.update(self.__count)

    def end(self):
        self.waitBar.finish()
        self.waitBar.reparentTo(self.gui)
        self.title.reparentTo(self.gui)
        self.gui.reparentTo(hidden)
        return (self.__expectedCount, self.__count)

    def abort(self):
        self.gui.reparentTo(hidden)

    def tick(self):
        self.__count = self.__count + 1
        self.waitBar.update(self.__count)
