from panda3d.core import *
from direct.gui.DirectGui import *
from direct.directnotify import DirectNotifyGlobal
from direct.task.Task import Task
from . import ShtikerPage
from toontown.toonbase import TTLocalizer
from toontown.toonbase import ToontownGlobals
from toontown.toontowngui import TTDialog
from toontown.hood import ZoneUtil
from toontown.friends import ToonGroupsGlobals as G


class GroupsPage(ShtikerPage.ShtikerPage):
    """The Groups page of the sticker book: the group tracker. Left page: the open groups. Right page: the group picked (with Join),
    your own group (with End/Leave), or the list of things to post a group for. Talks to ToonPresence (toontown/friends)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('GroupsPage')
    REFRESH = 5.0

    def __init__(self):
        ShtikerPage.ShtikerPage.__init__(self)
        self.groups = []
        self.groupById = {}
        self.mine = 0
        self.selectedId = None
        self.posting = False
        self.buttons = []
        self.scrollList = None
        self.confirm = None
        self.joining = None
        self.goAfterJoin = False

    def load(self):
        self.title = DirectLabel(parent=self, relief=None, text=TTLocalizer.GroupsPageTitle, text_scale=0.12, textMayChange=0, pos=(0, 0, 0.6))
        self.helpText = DirectLabel(parent=self, relief=None, text=TTLocalizer.GroupsPageIntro, text_scale=0.06, text_wordwrap=12, text_align=TextNode.ALeft, textMayChange=1, pos=(0.058, 0, 0.403))
        self.gui = loader.loadModel('phase_3.5/models/gui/friendslist_gui')
        self.listX, self.listSizeX, self.listZ, self.listSizeZ = -0.02, 0.67, -0.96, 1.04
        self.itemX, self.itemZ = -0.237, 0.365
        self.buttonX = self.itemX + 0.293
        self.__makeScrollList()
        self.emptyText = DirectLabel(parent=self, relief=None, text=TTLocalizer.GroupsPageEmpty, text_scale=0.06, text_wordwrap=9, textMayChange=1, pos=(-0.42, 0, 0.1), sortOrder=10)
        DirectFrame(parent=self.scrollList, text=TTLocalizer.GroupsPageScrollTitle, text_scale=0.06, text_align=TextNode.ACenter, relief=None, pos=(self.buttonX, 0, self.itemZ + 0.127))
        self.__loadDetail()
        self.__loadPostMenu()

    def __makeScrollList(self):
        selected = 0
        if self.scrollList:
            selected = self.scrollList.getSelectedIndex()
            for b in self.buttons:
                b.detachNode()
            self.scrollList.destroy()
        g = self.gui
        arrow = (g.find('**/FndsLst_ScrollUp'), g.find('**/FndsLst_ScrollDN'), g.find('**/FndsLst_ScrollUp_Rllvr'), g.find('**/FndsLst_ScrollUp'))
        self.scrollList = DirectScrolledList(parent=self, relief=None, pos=(-0.5, 0, 0), incButton_image=arrow, incButton_relief=None,
         incButton_scale=(1.3, 1.3, -1.3), incButton_pos=(self.buttonX, 0, self.itemZ - 0.999), incButton_image3_color=Vec4(1, 1, 1, 0.2),
         decButton_image=arrow, decButton_relief=None, decButton_scale=(1.3, 1.3, 1.3), decButton_pos=(self.buttonX, 0, self.itemZ + 0.227),
         decButton_image3_color=Vec4(1, 1, 1, 0.2), itemFrame_pos=(self.itemX, 0, self.itemZ), itemFrame_scale=1.0, itemFrame_relief=DGG.SUNKEN,
         itemFrame_frameSize=(self.listX, self.listX + self.listSizeX, self.listZ, self.listZ + self.listSizeZ),
         itemFrame_frameColor=(0.85, 0.95, 1, 1), itemFrame_borderWidth=(0.01, 0.01), numItemsVisible=10, forceHeight=0.09, items=self.buttons)
        self.scrollList.scrollTo(selected)

    def __loadDetail(self):
        self.detail = NodePath('groupDetail')
        self.detail.reparentTo(self)
        self.detail.setPos(0.4, 0, 0)
        self.detailKind = DirectLabel(parent=self.detail, relief=None, text='', text_scale=0.075, text_fg=(0, 0, 0, 1), text_wordwrap=8, textMayChange=1, text_align=TextNode.ACenter, pos=(0, 0, 0.4))
        self.detailInfo = DirectLabel(parent=self.detail, relief=None, text='', text_scale=0.052, text_wordwrap=12, textMayChange=1, text_align=TextNode.ACenter, pos=(0, 0, 0.2))
        self.detailNote = DirectLabel(parent=self.detail, relief=None, text='', text_scale=0.048, text_fg=(0.55, 0.1, 0.1, 1), text_wordwrap=12, textMayChange=1, text_align=TextNode.ACenter, pos=(0, 0, -0.18))
        model = loader.loadModel('phase_3.5/models/gui/matching_game_gui')
        circle = model.find('**/minnieCircle')
        self.mainButton = DirectButton(parent=self.detail, relief=None, image=circle, image_scale=(1.3, 1, 1.3), image_color=(0.45, 0.9, 0.4, 1), text='', text_scale=0.055, text_pos=(0, 0.01), text_fg=(0, 0, 0, 1), textMayChange=1, pos=(0, 0, -0.5), command=self.__mainPressed)
        self.postButton = DirectButton(parent=self, relief=None, image=circle, image_scale=(1.0, 1, 1.0), image_color=(0.95, 0.85, 0.3, 1), text=TTLocalizer.GroupsPagePost, text_scale=0.045, text_pos=(0, 0.01), text_fg=(0, 0, 0, 1), pos=(0.4, 0, -0.45), command=self.__showPostMenu)
        self.goButton = DirectButton(parent=self.detail, relief=None, image=circle, image_scale=(1.3, 1, 1.3), image_color=(0.45, 0.8, 1, 1), text=TTLocalizer.GroupsPageGo, text_scale=0.055, text_pos=(0, 0.01), text_fg=(0, 0, 0, 1), pos=(-0.19, 0, -0.4), command=self.__goPressed)
        model.removeNode()
        self.detail.hide()

    CATEGORIES = [('Cog HQ Bosses', [G.KIND_SELLBOT_BOSS, G.KIND_CASHBOT_BOSS, G.KIND_LAWBOT_BOSS, G.KIND_BOSSBOT_BOSS]),
                  ('Cog Facilities', [G.KIND_FACTORY, G.KIND_MINT, G.KIND_OFFICE, G.KIND_GOLF, G.KIND_COGDO]),
                  ('Buildings and Invasions', [G.KIND_BUILDING, G.KIND_SELLBOT_BLDG, G.KIND_CASHBOT_BLDG, G.KIND_LAWBOT_BLDG, G.KIND_BOSSBOT_BLDG, G.KIND_INVASION])]

    def __loadPostMenu(self):
        """Posting is two taps on big buttons: a group of activities, then the activity."""
        self.postMenu = NodePath('groupPostMenu')
        self.postMenu.reparentTo(self)
        self.postMenu.setPos(0.4, 0, 0)
        self.postTitle = DirectLabel(parent=self.postMenu, relief=None, text=TTLocalizer.GroupsPagePostTitle, text_scale=0.065, text_wordwrap=9, textMayChange=1, pos=(0, 0, 0.5))
        self.menuButtons = []
        self.backButton = DirectButton(parent=self.postMenu, relief=DGG.RAISED, borderWidth=(0.01, 0.01), frameColor=(1, 0.8, 0.8, 1), frameSize=(-0.2, 0.2, -0.05, 0.065), text=TTLocalizer.GroupsPageBack, text_scale=0.06, text_fg=(0.55, 0.1, 0.1, 1), pos=(0, 0, -0.6), command=self.__menuBack)
        self.postMenu.hide()
        self.menuLevel = 0

    def __fillMenu(self, entries):
        """entries: (label, command, args). One big button per row, 0.115 apart."""
        for b in self.menuButtons:
            b.destroy()
        self.menuButtons = []
        top = 0.37
        for i, (label, command, args) in enumerate(entries):
            self.menuButtons.append(DirectButton(parent=self.postMenu, relief=DGG.RAISED, borderWidth=(0.012, 0.012), frameColor=(0.75, 0.9, 1, 1), frameSize=(-0.36, 0.36, -0.045, 0.065),
                                                 text=label, text_scale=0.056, text_pos=(0, -0.012), pos=(0, 0, top - i * 0.115), command=command, extraArgs=args))

    def __showPostMenu(self):
        self.detail.hide()
        self.helpText.hide()
        self.postButton.hide()
        self.menuLevel = 0
        self.postTitle['text'] = TTLocalizer.GroupsPagePostTitle
        self.__fillMenu([(name, self.__openCategory, [i]) for i, (name, kinds) in enumerate(self.CATEGORIES)])
        self.postMenu.show()

    def __openCategory(self, index):
        self.menuLevel = 1
        name, kinds = self.CATEGORIES[index]
        self.postTitle['text'] = name
        self.__fillMenu([(TTLocalizer.GroupKindNames[k], self.__postKind, [k]) for k in kinds])

    def __menuBack(self):
        if self.menuLevel == 1:
            self.__showPostMenu()
        else:
            self.__hidePostMenu()

    def unload(self):
        taskMgr.remove('GroupsPageRefresh')
        self.__closeConfirm()
        self.detail.removeNode()
        self.postMenu.removeNode()
        self.gui.removeNode()
        self.scrollList.destroy()
        del self.scrollList
        del self.buttons
        del self.title
        ShtikerPage.ShtikerPage.unload(self)

    # ---- the book opening and closing
    def enter(self):
        ShtikerPage.ShtikerPage.enter(self)
        self.accept('toonGroupList', self.__gotList)
        self.accept('toonGroupResult', self.__gotResult)
        self.__refresh()

    def exit(self):
        self.ignore('toonGroupList')
        self.ignore('toonGroupResult')
        taskMgr.remove('GroupsPageRefresh')
        self.__closeConfirm()
        self.__hidePostMenu()
        self.joining = None
        ShtikerPage.ShtikerPage.exit(self)

    def __refresh(self, task=None):
        base.cr.toonPresence.up_groupListRequest()
        taskMgr.doMethodLater(self.REFRESH, self.__refresh, 'GroupsPageRefresh')
        return Task.done

    # ---- the list
    def __gotList(self, mine, groups):
        self.mine = mine
        self.groups = groups
        self.groupById = {g['id']: g for g in groups}
        if self.selectedId not in self.groupById:
            self.selectedId = mine if mine in self.groupById else None
        self.buttons = []
        for g in groups:
            self.buttons.append(self.__makeButton(g))
        self.__makeScrollList()
        self.emptyText['text'] = TTLocalizer.GroupsPageEmpty
        if groups:
            self.emptyText.hide()
        else:
            self.emptyText.show()
        self.__showDetail()

    def __makeButton(self, g):
        full = g['size'] >= g['max']
        if g['id'] == self.mine:
            color = Vec4(0.15, 0.6, 0.15, 1)
        elif full:
            color = Vec4(0.5, 0.5, 0.5, 1)
        else:
            color = Vec4(0, 0, 0, 1)
        short = TTLocalizer.GroupKindShort.get(g['kind'], '?')
        text = '%s %d/%d  %s' % (short, g['size'], g['max'], g['name'][:12])
        selected = Vec4(1, 1, 0, 1) if g['id'] == self.selectedId else Vec4(0, 0, 0, 0)
        return DirectButton(relief=None, text=text, text_scale=0.056, text_align=TextNode.ALeft, text_fg=color, text_bg=selected, text1_bg=Vec4(0.5, 0.9, 1, 1), text2_bg=Vec4(1, 1, 0, 1), command=self.__select, extraArgs=[g['id']])

    def __select(self, groupId):
        self.selectedId = groupId
        self.posting = False
        self.__hidePostMenu()
        for g, b in zip(self.groups, self.buttons):
            b['text_bg'] = Vec4(1, 1, 0, 1) if g['id'] == groupId else Vec4(0, 0, 0, 0)
        self.__showDetail()

    # ---- the right page
    def __showDetail(self):
        g = self.groupById.get(self.selectedId)
        if self.postMenu.isHidden() is False:
            return
        self.postButton.show() if not self.mine else self.postButton.hide()
        # with a group open its Join button takes the lower right, so Post a Group goes under it; alone it sits higher up
        self.postButton.setPos(0.4, 0, -0.62 if g is not None else -0.45)
        self.postButton.setScale(0.8 if g is not None else 1.0)
        self.mainButton.setZ(-0.4)
        self.mainButton.setX(0)
        self.goButton.hide()
        self.detailNote.setZ(-0.1)
        if g is None:
            self.detail.hide()
            self.helpText.show()
            return
        self.helpText.hide()
        self.detail.show()
        shardName = base.cr.getShardName(g['shard']) or ''
        hoodName = ''
        try:
            hoodName = base.cr.hoodMgr.getFullnameFromId(g['hood'])
        except Exception:
            pass
        self.detailKind['text'] = TTLocalizer.GroupKindNames.get(g['kind'], '?')
        lines = [TTLocalizer.GroupsPageHost % g['name'], TTLocalizer.GroupsPageSize % (g['size'], g['max'])]
        if shardName:
            lines.append(TTLocalizer.GroupsPageHelpDistrict % shardName)
        if hoodName:
            lines.append(hoodName)
        lines.append(self.__ageText(g['age']))
        self.detailInfo['text'] = '\n'.join(lines)
        full = g['size'] >= g['max']
        if g['id'] == self.mine:
            hosting = self.__hosting()
            self.mainButton['text'] = TTLocalizer.GroupsPageDisband if hosting else TTLocalizer.GroupsPageLeave
            self.mainButton['image_color'] = Vec4(1, 0.5, 0.5, 1)
            self.detailNote['text'] = TTLocalizer.GroupsPageEndsWithYou if hosting else TTLocalizer.GroupsPageYouJoined
            self.mainButton.show()
            if not hosting and not self.book.safeMode:
                # a member can walk to the host whenever it likes: Go to Group on the left, Leave on the right
                self.goButton.show()
                self.mainButton.setX(0.19)
        elif full:
            self.detailNote['text'] = TTLocalizer.GroupsPageFull
            self.mainButton.hide()
        elif self.book.safeMode:
            self.detailNote['text'] = ''
            self.mainButton.hide()
        else:
            self.mainButton['text'] = TTLocalizer.GroupsPageJoin
            self.mainButton['image_color'] = Vec4(0.45, 0.9, 0.4, 1)
            self.detailNote['text'] = ''
            self.mainButton.show()

    def __hosting(self):
        return bool(self.mine) and self.mine == getattr(base.cr.toonPresence, 'hostedGroupId', None)

    @staticmethod
    def __ageText(seconds):
        if seconds < 60:
            return TTLocalizer.GroupsPageAgeNow
        if seconds < 3600:
            return TTLocalizer.GroupsPageAge % (TTLocalizer.GroupsPageMinutes % (seconds // 60))
        return TTLocalizer.GroupsPageAge % (TTLocalizer.GroupsPageHours % (seconds // 3600))

    def __mainPressed(self):
        g = self.groupById.get(self.selectedId)
        if g is None:
            return
        if g['id'] == self.mine:
            if self.__hosting():
                base.cr.toonPresence.up_groupDisband()
            else:
                base.cr.toonPresence.up_groupLeave()
        else:
            self.joining = g['id']
            self.goAfterJoin = False
            base.cr.toonPresence.up_groupJoin(g['id'])

    def __goPressed(self):
        """Go to the host of the group this toon is in. Asking to join again just answers where the host is now."""
        if not self.mine:
            return
        self.joining = self.mine
        self.goAfterJoin = True
        base.cr.toonPresence.up_groupJoin(self.mine)

    # ---- posting
    def __hidePostMenu(self):
        if hasattr(self, 'postMenu') and not self.postMenu.isEmpty():
            self.postMenu.hide()
            self.__showDetail()

    def __postKind(self, kind):
        self.postMenu.hide()
        if not base.cr.toonPresence.up_groupPost(kind, G.KINDS[kind]):
            self.__say(TTLocalizer.GroupsPageNoPlace)
            self.__showDetail()

    # ---- answers
    def __gotResult(self, op, code, groupId, shard, hood, zone):
        if op == G.OP_POST:
            if code == G.OK:
                self.selectedId = groupId
                self.__say(TTLocalizer.GroupsPagePosted)
            else:
                self.__say(self.__codeText(code))
            self.__refreshNow()
        elif op == G.OP_JOIN:
            if code == G.OK and self.joining == groupId:
                self.joining = None
                self.__refreshNow()
                if self.goAfterJoin:
                    self.goAfterJoin = False
                    self.__teleport(groupId, shard, hood, zone)
                else:
                    self.__say(TTLocalizer.GroupsPageJoinedOk)
            elif code != G.OK:
                self.__say(self.__codeText(code))
                self.__refreshNow()
        elif op in (G.OP_CLOSED, G.OP_LEAVE):
            if op == G.OP_CLOSED:
                self.__say(TTLocalizer.GroupsPageClosed)
            gone = groupId if op == G.OP_CLOSED else self.mine
            self.selectedId = None
            self.__gotList(0, [g for g in self.groups if g['id'] != gone])
            self.__refreshNow()

    @staticmethod
    def __codeText(code):
        return {G.GONE: TTLocalizer.GroupsPageGone, G.FULL: TTLocalizer.GroupsPageFullReject, G.BUSY: TTLocalizer.GroupsPageBusy,
                G.OWN: TTLocalizer.GroupsPageOwn}.get(code, TTLocalizer.GroupsPageBad)

    def __refreshNow(self):
        taskMgr.remove('GroupsPageRefresh')
        taskMgr.doMethodLater(1.2, self.__refresh, 'GroupsPageRefresh')      # the server answers one list a second

    def __teleport(self, groupId, shard, hood, zone):
        """Join worked: go to where the host is, the way Go To does."""
        canonical = ZoneUtil.getCanonicalZoneId(hood)
        if not hood or not shard:
            return self.__say(TTLocalizer.GroupsPageBad)
        if hood == ToontownGlobals.MyEstate:
            return self.__say(TTLocalizer.GroupsPageBad)
        if canonical not in base.localAvatar.hoodsVisited + ToontownGlobals.HoodsAlwaysVisited:
            return self.__say(TTLocalizer.TeleportPanelUnknownHood % base.cr.hoodMgr.getFullnameFromId(hood))
        if canonical not in base.cr.hoodMgr.getAvailableZones():
            return self.__say(TTLocalizer.TeleportPanelUnavailableHood % base.cr.hoodMgr.getFullnameFromId(hood))
        if shard == base.localAvatar.defaultShard:
            shard = None
        try:
            place = base.cr.playGame.getPlace()
            if place is None:
                place = base.cr.playGame.hood.place
            place.requestTeleport(hood, zone, shard, -1)
        except Exception:
            self.notify.warning('could not teleport to group %s' % groupId, exc_info=True)
            self.__say(TTLocalizer.GroupsPageBad)

    # ---- a small message box
    def __say(self, text):
        self.__closeConfirm()
        self.confirm = TTDialog.TTGlobalDialog(doneEvent='groupsConfirmDone', message=text, style=TTDialog.Acknowledge)
        self.confirm.show()
        self.accept('groupsConfirmDone', self.__closeConfirm)

    def __closeConfirm(self):
        self.ignore('groupsConfirmDone')
        if self.confirm:
            self.confirm.cleanup()
            self.confirm = None
