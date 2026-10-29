from panda3d.core import *
from . import ShtikerPage
from direct.task.Task import Task
from direct.gui.DirectGui import *
from panda3d.core import *
from toontown.toonbase import TTLocalizer
from direct.directnotify import DirectNotifyGlobal
from toontown.hood import ZoneUtil
from toontown.toonbase import ToontownGlobals
from toontown.distributed import ToontownDistrictStats
from toontown.toontowngui import TTDialog
from toontown.battle import SuitBattleGlobals
from toontown.suit import Suit
import functools
POP_COLORS_NTT = (Vec4(0.0, 1.0, 0.0, 1.0), Vec4(1.0, 1.0, 0.0, 1.0), Vec4(1.0, 0.0, 0.0, 1.0))
POP_COLORS = (Vec4(0.4, 0.4, 1.0, 1.0), Vec4(0.4, 1.0, 0.4, 1.0), Vec4(1.0, 0.4, 0.4, 1.0))

class ShardPage(ShtikerPage.ShtikerPage):
    notify = DirectNotifyGlobal.directNotify.newCategory('ShardPage')

    def __init__(self):
        ShtikerPage.ShtikerPage.__init__(self)
        self.shardButtonMap = {}
        self.shardButtons = []
        self.scrollList = None
        self.textRolloverColor = Vec4(1, 1, 0, 1)
        self.textDownColor = Vec4(0.5, 0.9, 1, 1)
        self.textDisabledColor = Vec4(0.4, 0.8, 0.4, 1)
        self.ShardInfoUpdateInterval = 5.0
        self.lowPop, self.midPop, self.highPop = base.getShardPopLimits()
        self.showPop = config.GetBool('show-total-population', 0)
        self.selectedShardId = None
        self.shardInfo = {}
        self.nameColors = {}
        self.noTeleport = config.GetBool('shard-page-disable', 0)
        return

    def load(self):
        main_text_scale = 0.06
        title_text_scale = 0.12
        self.title = DirectLabel(parent=self, relief=None, text=TTLocalizer.ShardPageTitle, text_scale=title_text_scale, textMayChange=0, pos=(0, 0, 0.6))
        helpText_ycoord = 0.403
        self.helpText = DirectLabel(parent=self, relief=None, text='', text_scale=main_text_scale, text_wordwrap=12, text_align=TextNode.ALeft, textMayChange=1, pos=(0.058, 0, helpText_ycoord))
        shardPop_ycoord = helpText_ycoord - 0.523
        totalPop_ycoord = shardPop_ycoord - 0.26
        self.totalPopulationText = DirectLabel(parent=self, relief=None, text=TTLocalizer.ShardPagePopulationTotal % 1, text_scale=0.058, text_fg=(0.55, 0.1, 0.1, 1), textMayChange=1, text_align=TextNode.ACenter, pos=(0, 0, 0.5))
        self.__loadDetails()
        self.gui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        self.listXorigin = -0.02
        self.listFrameSizeX = 0.67
        self.listZorigin = -0.96
        self.listFrameSizeZ = 1.04
        self.arrowButtonScale = 1.3
        self.itemFrameXorigin = -0.237
        self.itemFrameZorigin = 0.365
        self.buttonXstart = self.itemFrameXorigin + 0.293
        self.regenerateScrollList()
        scrollTitle = DirectFrame(parent=self.scrollList, text=TTLocalizer.ShardPageScrollTitle, text_scale=main_text_scale, text_align=TextNode.ACenter, relief=None, pos=(self.buttonXstart, 0, self.itemFrameZorigin + 0.127))
        return

    def __loadDetails(self):
        """The panel on the right page: the District picked in the list, its population, any Cog invasion and the teleport button."""
        self.detail = NodePath('shardDetail')
        self.detail.reparentTo(self)
        self.detail.setPos(0.4, 0, 0)
        self.detailName = DirectLabel(parent=self.detail, relief=None, text='', text_scale=0.105, text_fg=(0, 0, 0, 1), textMayChange=1, text_align=TextNode.ACenter, pos=(0, 0, 0.36))
        self.detailPop = DirectLabel(parent=self.detail, relief=None, text='', text_scale=0.062, textMayChange=1, text_align=TextNode.ACenter, pos=(0, 0, 0.25))
        self.globe = NodePath('shardGlobe')
        self.globe.reparentTo(self.detail)
        icons = loader.loadModel('phase_3.5/models/gui/sos_textures')
        globeGeom = icons.find('**/district')
        if not globeGeom.isEmpty():
            globeGeom.copyTo(self.globe)
            a, b = Point3(), Point3()
            self.globe.calcTightBounds(a, b)
            size = max(b.x - a.x, b.z - a.z, 0.001)
            k = 0.5 / size
            self.globe.setScale(k)
            self.globe.setPos(-(a.x + b.x) / 2 * k, 0, -0.02 - (a.z + b.z) / 2 * k)
        icons.removeNode()
        self.cogHead = None
        self.invasionText = DirectLabel(parent=self.detail, relief=None, text='', text_scale=0.052, text_fg=(0.85, 0.1, 0.1, 1), text_wordwrap=12, textMayChange=1, text_align=TextNode.ACenter, pos=(0, 0, -0.3))
        model = loader.loadModel('phase_3.5/models/gui/matching_game_gui')
        circle = model.find('**/minnieCircle')
        self.teleportButton = DirectButton(parent=self.detail, relief=None, image=circle, image_scale=(1.3, 1, 1.3), image_color=(0.45, 0.9, 0.4, 1), text='Teleport\nHere!', text_scale=0.048, text_pos=(0, 0.01), text_fg=(0, 0, 0, 1), pos=(0, 0, -0.5), command=self.teleportToSelected)
        model.removeNode()
        self.detail.hide()

    def unload(self):
        if self.cogHead:
            self.cogHead.removeNode()
        self.detail.removeNode()
        self.gui.removeNode()
        del self.title
        self.scrollList.destroy()
        del self.scrollList
        del self.shardButtons
        taskMgr.remove('ShardPageUpdateTask-doLater')
        ShtikerPage.ShtikerPage.unload(self)

    def regenerateScrollList(self):
        selectedIndex = 0
        if self.scrollList:
            selectedIndex = self.scrollList.getSelectedIndex()
            for button in self.shardButtons:
                button.detachNode()

            self.scrollList.destroy()
            self.scrollList = None
        self.scrollList = DirectScrolledList(parent=self, relief=None, pos=(-0.5, 0, 0), incButton_image=(self.gui.find('**/FndsLst_ScrollUp'),
         self.gui.find('**/FndsLst_ScrollDN'),
         self.gui.find('**/FndsLst_ScrollUp_Rllvr'),
         self.gui.find('**/FndsLst_ScrollUp')), incButton_relief=None, incButton_scale=(self.arrowButtonScale, self.arrowButtonScale, -self.arrowButtonScale), incButton_pos=(self.buttonXstart, 0, self.itemFrameZorigin - 0.999), incButton_image3_color=Vec4(1, 1, 1, 0.2), decButton_image=(self.gui.find('**/FndsLst_ScrollUp'),
         self.gui.find('**/FndsLst_ScrollDN'),
         self.gui.find('**/FndsLst_ScrollUp_Rllvr'),
         self.gui.find('**/FndsLst_ScrollUp')), decButton_relief=None, decButton_scale=(self.arrowButtonScale, self.arrowButtonScale, self.arrowButtonScale), decButton_pos=(self.buttonXstart, 0, self.itemFrameZorigin + 0.227), decButton_image3_color=Vec4(1, 1, 1, 0.2), itemFrame_pos=(self.itemFrameXorigin, 0, self.itemFrameZorigin), itemFrame_scale=1.0, itemFrame_relief=DGG.SUNKEN, itemFrame_frameSize=(self.listXorigin,
         self.listXorigin + self.listFrameSizeX,
         self.listZorigin,
         self.listZorigin + self.listFrameSizeZ), itemFrame_frameColor=(0.85, 0.95, 1, 1), itemFrame_borderWidth=(0.01, 0.01), numItemsVisible=15, forceHeight=0.065, items=self.shardButtons)
        self.scrollList.scrollTo(selectedIndex)
        return

    def askForShardInfoUpdate(self, task = None):
        ToontownDistrictStats.refresh('shardInfoUpdated')
        taskMgr.doMethodLater(self.ShardInfoUpdateInterval, self.askForShardInfoUpdate, 'ShardPageUpdateTask-doLater')
        return Task.done

    def makeShardButton(self, shardId, shardName, shardPop, nameColor=Vec4(0, 0, 0, 1)):
        shardButtonParent = DirectFrame()
        shardButtonL = DirectButton(parent=shardButtonParent, relief=None, text=shardName, text_scale=0.06, text_align=TextNode.ALeft, text_fg=nameColor, text1_bg=self.textDownColor, text2_bg=self.textRolloverColor, text3_fg=self.textDisabledColor, textMayChange=1, command=self.selectShard, extraArgs=[shardId])
        if self.showPop:
            popText = str(shardPop)
            if shardPop == None:
                popText = ''
            shardButtonR = DirectButton(parent=shardButtonParent, relief=None, text=popText, text_scale=0.06, text_align=TextNode.ALeft, text1_bg=self.textDownColor, text2_bg=self.textRolloverColor, text3_fg=self.textDisabledColor, textMayChange=1, pos=(0.5, 0, 0), command=self.selectShard, extraArgs=[shardId])
        else:
            model = loader.loadModel('phase_3.5/models/gui/matching_game_gui')
            button = model.find('**/minnieCircle')
            shardButtonR = DirectButton(parent=shardButtonParent, relief=None, image=button, image_scale=(0.3, 1, 0.3), image2_scale=(0.35, 1, 0.35), image_color=self.getPopColor(shardPop), pos=(0.6, 0, 0.0125), text=self.getPopText(shardPop), text_scale=0.06, text_align=TextNode.ACenter, text_pos=(-0.0125, -0.0125), text_fg=Vec4(0, 0, 0, 0), text1_fg=Vec4(0, 0, 0, 0), text2_fg=Vec4(0, 0, 0, 1), text3_fg=Vec4(0, 0, 0, 0), command=self.selectShard, extraArgs=[shardId])
            del model
            del button
        return (shardButtonParent, shardButtonR, shardButtonL)

    def getPopColor(self, pop):
        if base.cr.productName == 'JP':
            if pop < self.midPop:
                color1 = POP_COLORS_NTT[0]
                color2 = POP_COLORS_NTT[1]
                popRange = self.midPop - self.lowPop
                pop = pop - self.lowPop
            else:
                color1 = POP_COLORS_NTT[1]
                color2 = POP_COLORS_NTT[2]
                popRange = self.highPop - self.midPop
                pop = pop - self.midPop
            popPercent = pop / float(popRange)
            if popPercent > 1:
                popPercent = 1
            newColor = color2 * popPercent + color1 * (1 - popPercent)
        elif pop <= self.lowPop:
            newColor = POP_COLORS[0]
        elif pop <= self.midPop:
            newColor = POP_COLORS[1]
        else:
            newColor = POP_COLORS[2]
        return newColor

    def getPopText(self, pop):
        if pop <= self.lowPop:
            popText = TTLocalizer.ShardPageLow
        elif pop <= self.midPop:
            popText = TTLocalizer.ShardPageMed
        else:
            popText = TTLocalizer.ShardPageHigh
        return popText

    def getPopChoiceHandler(self, pop):
        if base.cr.productName == 'JP':
            handler = self.choseShard
        elif pop <= self.midPop:
            if self.noTeleport and not self.showPop:
                handler = self.shardChoiceReject
            else:
                handler = self.choseShard
        elif self.showPop:
            handler = self.choseShard
        else:
            handler = self.shardChoiceReject
        return handler

    def getCurrentZoneId(self):
        try:
            zoneId = base.cr.playGame.getPlace().getZoneId()
        except:
            zoneId = None

        return zoneId

    def getCurrentShardId(self):
        zoneId = self.getCurrentZoneId()
        if zoneId != None and ZoneUtil.isWelcomeValley(zoneId):
            return ToontownGlobals.WelcomeValleyToken
        else:
            return base.localAvatar.defaultShard
        return

    def updateScrollList(self):
        curShardTuples = base.cr.listActiveShards()

        def compareShardTuples(a, b):
            if a[1] < b[1]:
                return -1
            elif b[1] < a[1]:
                return 1
            else:
                return 0

        curShardTuples.sort(key=functools.cmp_to_key(compareShardTuples))
        if base.cr.welcomeValleyManager:
            curShardTuples.append((ToontownGlobals.WelcomeValleyToken,
             TTLocalizer.WelcomeValley[-1],
             0,
             0))
        currentShardId = self.getCurrentShardId()
        actualShardId = base.localAvatar.defaultShard
        actualShardName = None
        anyChanges = 0
        totalPop = 0
        totalWVPop = 0
        currentMap = {}
        self.shardButtons = []
        for i in range(len(curShardTuples)):
            shardId, name, pop, WVPop = curShardTuples[i]
            totalPop += pop
            pop = max(0, pop - WVPop)        # a district's count is for its own streets: the Welcome Valley toons are listed under Welcome Valley
            if shardId == actualShardId:
                actualShardName = name
            totalWVPop += WVPop
            currentMap[shardId] = 1
            district = base.cr.activeDistrictMap.get(shardId)
            invasion = getattr(district, 'invasionCog', '') if district else ''
            if invasion:
                nameColor = Vec4(0.9, 0.05, 0.05, 1)
            elif shardId == currentShardId:
                nameColor = Vec4(0.3, 0.75, 0.3, 1)
            else:
                nameColor = Vec4(0, 0, 0, 1)
            buttonTuple = self.shardButtonMap.get(shardId)
            if buttonTuple != None and self.nameColors.get(shardId) != tuple(nameColor):
                # the colour is fixed when the button is made, so a change of state means a new button
                buttonTuple[0].destroy()
                buttonTuple = None
            if buttonTuple == None:
                self.nameColors[shardId] = tuple(nameColor)
                buttonTuple = self.makeShardButton(shardId, name, pop, nameColor)
                self.shardButtonMap[shardId] = buttonTuple
                anyChanges = 1
            elif self.showPop:
                buttonTuple[1]['text'] = str(pop)
            else:
                buttonTuple[1]['image_color'] = self.getPopColor(pop)
                if not base.cr.productName == 'JP':
                    buttonTuple[1]['text'] = self.getPopText(pop)
            self.shardButtons.append(buttonTuple[0])
            self.shardInfo[shardId] = (name, pop, invasion, getattr(district, 'invasionSkeleton', 0), getattr(district, 'invasionRemaining', 0))
            # the list says it at a glance: green is where you are, red has an invasion
            buttonTuple[2]['text_bg'] = self.textRolloverColor if shardId == self.selectedShardId else Vec4(0, 0, 0, 0)
            buttonTuple[1]['state'] = DGG.NORMAL
            buttonTuple[2]['state'] = DGG.NORMAL

        for shardId, buttonTuple in list(self.shardButtonMap.items()):
            if shardId not in currentMap:
                buttonTuple[0].destroy()
                del self.shardButtonMap[shardId]
                anyChanges = 1

        buttonTuple = self.shardButtonMap.get(ToontownGlobals.WelcomeValleyToken)
        if buttonTuple:
            if self.showPop:
                buttonTuple[1]['text'] = str(totalWVPop)
            else:
                buttonTuple[1]['image_color'] = self.getPopColor(totalWVPop)
                if not base.cr.productName == 'JP':
                    buttonTuple[1]['text'] = self.getPopText(totalWVPop)
            self.shardInfo[ToontownGlobals.WelcomeValleyToken] = (TTLocalizer.WelcomeValley[-1], totalWVPop, '', 0, 0)
        if anyChanges:
            self.regenerateScrollList()
        self.totalPopulationText['text'] = TTLocalizer.ShardPagePopulationTotal % totalPop
        helpText = TTLocalizer.ShardPageHelpIntro
        if actualShardName:
            if currentShardId == ToontownGlobals.WelcomeValleyToken:
                helpText += TTLocalizer.ShardPageHelpWelcomeValley % actualShardName
            else:
                helpText += TTLocalizer.ShardPageHelpWhere % actualShardName
        if not self.book.safeMode:
            helpText += TTLocalizer.ShardPageHelpMove
        self.helpText['text'] = helpText
        self.showDetails()
        return

    def selectShard(self, shardId):
        self.selectedShardId = shardId
        for sid, buttonTuple in self.shardButtonMap.items():
            buttonTuple[2]['text_bg'] = self.textRolloverColor if sid == shardId else Vec4(0, 0, 0, 0)
        self.showDetails()

    def showDetails(self):
        """Fill the right page from the District picked in the list (the intro text shows until one is)."""
        info = self.shardInfo.get(self.selectedShardId)
        if info is None:
            self.selectedShardId = None
            self.detail.hide()
            self.helpText.show()
            return
        name, pop, invasion, skeleton, remaining = info
        self.helpText.hide()
        self.detail.show()
        invading = bool(invasion) and invasion in SuitBattleGlobals.SuitAttributes
        self.detailName['text'] = name
        self.detailName['text_fg'] = Vec4(0.85, 0.1, 0.1, 1) if invading else Vec4(0, 0, 0, 1)
        self.detailPop['text'] = TTLocalizer.ShardPagePopulation % pop
        if self.cogHead:
            self.cogHead.removeNode()
            self.cogHead = None
        if invading:
            plural = TTLocalizer.SkeletonP if skeleton else SuitBattleGlobals.SuitAttributes[invasion]['pluralname']
            self.invasionText['text'] = TTLocalizer.ShardPageInvasion % plural
            try:
                self.cogHead = Suit.attachSuitHead(self.detail, invasion)
                self.cogHead.setScale(self.cogHead.getScale() * 1.2)
                self.cogHead.setPos(0.5, 0, -0.1)         # beside the globe: nearer the middle it covered the population line
            except Exception:
                self.notify.warning('could not show the invading Cog head')
                self.cogHead = None
        else:
            self.invasionText['text'] = ''
        if self.selectedShardId == self.getCurrentShardId() or self.book.safeMode:
            self.teleportButton.hide()
        else:
            self.teleportButton.show()

    def teleportToSelected(self):
        shardId = self.selectedShardId
        info = self.shardInfo.get(shardId)
        if shardId is None or info is None:
            return
        if self.getPopChoiceHandler(info[1]) == self.shardChoiceReject:
            self.shardChoiceReject(shardId)
        else:
            self.choseShard(shardId)

    def enter(self):
        self.askForShardInfoUpdate()
        self.updateScrollList()
        currentShardId = self.getCurrentShardId()
        buttonTuple = self.shardButtonMap.get(currentShardId)
        if buttonTuple:
            i = self.shardButtons.index(buttonTuple[0])
            self.scrollList.scrollTo(i, centered=1)
        ShtikerPage.ShtikerPage.enter(self)
        self.accept('shardInfoUpdated', self.updateScrollList)

    def exit(self):
        self.ignore('shardInfoUpdated')
        self.ignore('confirmDone')
        taskMgr.remove('ShardPageUpdateTask-doLater')
        ShtikerPage.ShtikerPage.exit(self)

    def shardChoiceReject(self, shardId):
        self.confirm = TTDialog.TTGlobalDialog(doneEvent='confirmDone', message=TTLocalizer.ShardPageChoiceReject, style=TTDialog.Acknowledge)
        self.confirm.show()
        self.accept('confirmDone', self.__handleConfirm)

    def __handleConfirm(self):
        self.ignore('confirmDone')
        self.confirm.cleanup()
        del self.confirm

    def choseShard(self, shardId):
        zoneId = self.getCurrentZoneId()
        canonicalHoodId = ZoneUtil.getCanonicalHoodId(base.localAvatar.lastHood)
        currentShardId = self.getCurrentShardId()
        if shardId == currentShardId:
            return
        elif shardId == ToontownGlobals.WelcomeValleyToken:
            self.doneStatus = {'mode': 'teleport',
             'hood': ToontownGlobals.WelcomeValleyToken}
            messenger.send(self.doneEvent)
        elif shardId == base.localAvatar.defaultShard:
            self.doneStatus = {'mode': 'teleport',
             'hood': canonicalHoodId}
            messenger.send(self.doneEvent)
        else:
            try:
                place = base.cr.playGame.getPlace()
            except:
                try:
                    place = base.cr.playGame.hood.loader.place
                except:
                    place = base.cr.playGame.hood.place

            place.requestTeleport(canonicalHoodId, canonicalHoodId, shardId, -1)
