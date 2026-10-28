from otp.avatar import Avatar
from panda3d.core import *
from panda3d.otp import *
from direct.task import Task
import random
from panda3d.core import *
from direct.directnotify import DirectNotifyGlobal
AnimDict = {'cl': ()}
ModelDict = {'cl': 'phase_5.5/models/estate/Clara_pose2-'}
LODModelDict = {'cl': []}

class Char(Avatar.Avatar):
    notify = DirectNotifyGlobal.directNotify.newCategory('Char')

    def __init__(self):
        try:
            self.Char_initialized
        except:
            self.Char_initialized = 1
            Avatar.Avatar.__init__(self)
            self.setPickable(0)
            self.setPlayerType(NametagGroup.CCNonPlayer)
            self.dialogueArray = []
            self.chatterArray = [[], [], []]

    def delete(self):
        try:
            self.Char_deleted
        except:
            self.Char_deleted = 1
            self.unloadDialogue()
            Avatar.Avatar.delete(self)

    def updateCharDNA(self, newDNA):
        if newDNA.name != self.style.name:
            self.swapCharModel(newDNA)

    def setDNAString(self, dnaString):
        newDNA = CharDNA.CharDNA()
        newDNA.makeFromNetString(dnaString)
        self.setDNA(newDNA)

    def setDNA(self, dna):
        if self.style:
            self.updateCharDNA(dna)
        else:
            self.style = dna
            self.generateChar()
            self.initializeDropShadow()
            self.initializeNametag3d()
            self.nametag3d.setBin('fixed', 0)

    def setLODs(self):
        self.setLODNode()
        levelOneIn = base.config.GetInt('lod1-in', 50)
        levelOneOut = base.config.GetInt('lod1-out', 1)
        levelTwoIn = base.config.GetInt('lod2-in', 100)
        levelTwoOut = base.config.GetInt('lod2-out', 50)
        levelThreeIn = base.config.GetInt('lod3-in', 280)
        levelThreeOut = base.config.GetInt('lod3-out', 100)
        self.addLOD(LODModelDict[self.style.name][0], levelOneIn, levelOneOut)
        self.addLOD(LODModelDict[self.style.name][1], levelTwoIn, levelTwoOut)
        self.addLOD(LODModelDict[self.style.name][2], levelThreeIn, levelThreeOut)

    def generateChar(self):
        dna = self.style
        self._name = dna.getCharName()
        self.geoEyes = 0
        if len(LODModelDict[dna.name]) > 1:
            self.setLODs()
        filePrefix = ModelDict[dna.name]
        height = 3.0
        self.lodStrings = []
        for lod in LODModelDict[self.style.name]:
            self.lodStrings.append(str(lod))

        if self.lodStrings:
            for lodStr in self.lodStrings:
                if len(self.lodStrings) > 1:
                    lodName = lodStr
                else:
                    lodName = 'lodRoot'
                self.loadModel(filePrefix + lodStr, lodName=lodName)

        else:
            self.loadModel(filePrefix)
        animDict = {}
        animList = AnimDict[self.style.name]
        for anim in animList:
            animFilePrefix = filePrefix[:6] + str(anim[2]) + filePrefix[7:]
            animDict[anim[0]] = animFilePrefix + anim[1]

        for lodStr in self.lodStrings:
            if len(self.lodStrings) > 1:
                lodName = lodStr
            else:
                lodName = 'lodRoot'
            self.loadAnims(animDict, lodName=lodName)

        self.setHeight(height)
        self.loadDialogue(dna.name)
        self.ears = []
        self.eyes = None
        self.lpupil = None
        self.rpupil = None
        self.eyesOpen = None
        self.eyesClosed = None
        self.__blinkName = 'blink-' + self._name
        return

    def swapCharModel(self, charStyle):
        for lodStr in self.lodStrings:
            if len(self.lodStrings) > 1:
                lodName = lodStr
            else:
                lodName = 'lodRoot'
            self.removePart('modelRoot', lodName=lodName)

        self.setStyle(charStyle)
        self.generateChar()

    def getDialogue(self, type, length):
        sfxIndex = None
        if type == 'statementA' or type == 'statementB':
            if length == 1:
                sfxIndex = 0
            elif length == 2:
                sfxIndex = 1
            elif length >= 3:
                sfxIndex = 2
        elif type == 'question':
            sfxIndex = 3
        elif type == 'exclamation':
            sfxIndex = 4
        elif type == 'special':
            sfxIndex = 5
        else:
            self.notify.error('unrecognized dialogue type: ', type)
        if sfxIndex != None and sfxIndex < len(self.dialogueArray) and self.dialogueArray[sfxIndex] != None:
            return self.dialogueArray[sfxIndex]
        else:
            return
        return

    def playDialogue(self, type, length, delay = None):
        dialogue = self.getDialogue(type, length)
        base.playSfx(dialogue)

    def getChatterDialogue(self, category, msg):
        try:
            return self.chatterArray[category][msg]
        except IndexError:
            return None

        return None

    def getShadowJoint(self):
        return self.getGeomNode()

    def getNametagJoints(self):
        return []

    def loadChatterDialogue(self, name, audioIndexArray, loadPath, language):
        chatterTypes = ['greetings', 'comments', 'goodbyes']
        for categoryIndex in range(len(audioIndexArray)):
            chatterType = chatterTypes[categoryIndex]
            for fileIndex in audioIndexArray[categoryIndex]:
                if fileIndex:
                    self.chatterArray[categoryIndex].append(base.loader.loadSfx('%s/CC_%s_chatter_%s%02d.ogg' % (loadPath,
                     name,
                     chatterType,
                     fileIndex)))
                else:
                    self.chatterArray[categoryIndex].append(None)

        return

    def loadDialogue(self, char):
        if self.dialogueArray:
            self.notify.warning('loadDialogue() called twice.')
        self.unloadDialogue()
        if char == 'cl':
            dialogueFile = base.loader.loadSfx('phase_3.5/audio/dial/AV_dog_med.ogg')
            for i in range(0, 6):
                self.dialogueArray.append(dialogueFile)

        else:
            self.notify.error('unknown character %s' % char)

    def unloadDialogue(self):
        self.dialogueArray = []
        self.chatterArray = [[], [], []]

    def __blinkOpenEyes(self, task):
        self.openEyes()
        r = random.random()
        if r < 0.1:
            t = 0.2
        else:
            t = r * 4.0 + 1.0
        taskMgr.doMethodLater(t, self.__blinkCloseEyes, self.__blinkName)
        return Task.done

    def __blinkCloseEyes(self, task):
        self.closeEyes()
        taskMgr.doMethodLater(0.125, self.__blinkOpenEyes, self.__blinkName)
        return Task.done

    def openEyes(self):
        if self.geoEyes:
            for part in self.eyeOpenList:
                part.show()

            for part in self.eyeCloseList:
                part.hide()

        else:
            if self.eyes:
                self.eyes.setTexture(self.eyesOpen, 1)
            self.lpupil.show()
            self.rpupil.show()

    def closeEyes(self):
        if self.geoEyes:
            for part in self.eyeOpenList:
                part.hide()

            for part in self.eyeCloseList:
                part.show()

        else:
            if self.eyes:
                self.eyes.setTexture(self.eyesClosed, 1)
            self.lpupil.hide()
            self.rpupil.hide()

    def startBlink(self):
        if self.eyesOpen or self.geoEyes:
            taskMgr.remove(self.__blinkName)
            taskMgr.doMethodLater(random.random() * 4 + 1, self.__blinkCloseEyes, self.__blinkName)

    def stopBlink(self):
        if self.eyesOpen or self.geoEyes:
            taskMgr.remove(self.__blinkName)
            self.openEyes()

    def startEarTask(self):
        pass

    def stopEarTask(self):
        pass

    def uniqueName(self, idString):
        return idString + '-' + str(self.this)
