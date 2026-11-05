from . import ClothesGUI
from toontown.toon import ToonDNA

class MakeClothesGUI(ClothesGUI.ClothesGUI):
    notify = directNotify.newCategory('MakeClothesGUI')

    def __init__(self, doneEvent):
        ClothesGUI.ClothesGUI.__init__(self, ClothesGUI.CLOTHES_MAKETOON, doneEvent)

    def setupScrollInterface(self):
        self.dna = self.toon.getStyle()
        gender = self.dna.getGender()
        if gender != self.gender:
            self.tops = ToonDNA.getRandomizedTops(gender, tailorId=ToonDNA.MAKE_A_TOON)
            self.bottoms = ToonDNA.getRandomizedBottoms(gender, tailorId=ToonDNA.MAKE_A_TOON)
            # a makeover (MakeAToon sets keepOutfit) also offers the clothes the toon wears now, first, while it stays the same gender
            keep = getattr(self, 'keepOutfit', None)
            if keep and keep[0] == gender:
                if keep[1] not in self.tops:
                    self.tops.insert(0, keep[1])
                if keep[2] not in self.bottoms:
                    self.bottoms.insert(0, keep[2])
            self.gender = gender
            self.topChoice = 0
            self.bottomChoice = 0
        self.setupButtons()

    def setupButtons(self):
        ClothesGUI.ClothesGUI.setupButtons(self)
        if len(self.dna.torso) == 1:
            if self.gender == 'm':
                torsoStyle = 's'
            elif self.girlInShorts == 1:
                torsoStyle = 's'
            else:
                torsoStyle = 'd'
            self.toon.swapToonTorso(self.dna.torso[0] + torsoStyle)
            self.toon.loop('neutral', 0)
            self.toon.swapToonColor(self.dna)
            self.swapTop(0)
            self.swapBottom(0)
        return None
