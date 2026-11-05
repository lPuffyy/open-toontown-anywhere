"""Makeover: a toon that already exists goes back through Make-a-Toon (species, body, colours, clothes, and a new name if the player wants
one), for jellybeans. The price is gameconfig.json "makeover_beans" (default 1000), taken from the toon's jar first, then the bank.

The new look must be one Make-a-Toon could make, except that the toon may keep the clothes and colours it already had."""
from toontown.toon import ToonDNA
from toontown.toonbase import GameConfig

DEFAULT_COST = 1000

# answers from the server (AstronLoginManager.makeoverResponse)
OK = 0
NOT_ENOUGH_BEANS = 1
NOT_ALLOWED = 2
FAILED = 3


def cost():
    return int(GameConfig.get('makeover_beans', DEFAULT_COST))


def problem(oldNet, newNet):
    """Why the look in newNet can't replace oldNet, or '' when it can."""
    new = ToonDNA.ToonDNA()
    if not new.isValidNetString(newNet):
        return 'invalid dna'
    new.makeFromNetString(newNet)
    old = ToonDNA.ToonDNA()
    old.makeFromNetString(oldNet)
    gender = new.getGender()
    sameGender = gender == old.getGender()

    colours = ToonDNA.defaultBoyColorList if gender == 'm' else ToonDNA.defaultGirlColorList
    for part in ('headColor', 'armColor', 'legColor'):
        value = getattr(new, part)
        if value not in colours and value != getattr(old, part):
            return 'colour ' + part

    top = (new.topTex, new.topTexColor, new.sleeveTex, new.sleeveTexColor)
    oldTop = (old.topTex, old.topTexColor, old.sleeveTex, old.sleeveTexColor)
    if top not in ToonDNA.getTops(gender) and not (sameGender and top == oldTop):
        return 'top'
    bottom = (new.botTex, new.botTexColor)
    if bottom not in ToonDNA.getBottoms(gender) and not (sameGender and bottom == (old.botTex, old.botTexColor)):
        return 'bottom'

    # the torso's second letter says shorts ('s') or skirt ('d'), and has to match the bottoms
    if gender == 'm':
        wantStyle = 's'
    else:
        wantStyle = 'd' if ToonDNA.GirlBottoms[new.botTex][1] == ToonDNA.SKIRT else 's'
    if len(new.torso) != 2 or new.torso[1] != wantStyle:
        return 'torso'
    return ''
