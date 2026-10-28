"""Judges a name a player typed when making a toon, so the server can approve typed names itself.

The checks, in order:
  1. typed names switched off in gameconfig.json ("typed_names": "off")  -> rejected
  2. size: 2 to 24 characters, at most 4 words
  3. the game's own name rules (otp.namepanel.NameCheck: characters, capitals, vowels, punctuation) and no match with an NPC's name
  4. blocked words (below)
  5. not the same as a name another toon already has

Blocked words. The built-in lists are a STARTER set, kept ROT13-encoded so the repository does not spell the words out. Add your own to the
optional file /ot/data/blocked_names.txt (one word per line, "#" starts a comment; the file is read again when it changes):

    word        blocked as a whole word (also with a common ending: s, es, y, ed, er, ers, ing, head, face, hat, hole)
    *word       blocked anywhere inside a name (for words that are never innocent, like the strong built-in ones)
    !word       allowed: an innocent name that would otherwise be caught

Before matching, the name is flattened so common tricks do not work: capitals, accents and full-width letters are removed, letters from other
alphabets that look like Latin ones (a Cyrillic "o", a Greek "a") are turned into the Latin letter, look-alike characters (0 for o, 1 for i,
3 for e, 4 for a, 5 for s, 7 for t, @ for a, $ for s, ! for i) are turned into letters, spaces, dots and dashes between letters are ignored for
the "anywhere inside" words ("f u c k"), and repeated letters are shortened ("fuuuck"). A filter like this stops the obvious cases; it cannot
stop every determined player, so extend the file as you see names you do not want.
"""
import codecs
import os
import re
import time
import traceback
import unicodedata

from direct.directnotify import DirectNotifyGlobal

from otp.namepanel import NameCheck
from toontown.toonbase import GameConfig

notify = DirectNotifyGlobal.directNotify.newCategory('NameJudge')

# strong words count anywhere inside a name; weak ones (short, or common inside innocent words like Scunthorpe or Hancock) only as a whole word
_STRONG = ('shpx fuvg ovgpu juber fyhg avttre avttn snttbg ergneq crqbcuvyr cnrqbcuvyr zbyrfg qvyqb wvmm nffubyr nefrubyr onfgneq chffl cravf '
           'intvan uvgyre zbgureshpx pbpxfhpxre obyybpxf jnaxre gjng genaal oybjwbo unaqwbo evzwbo phzfubg betnfz znfgheong xvyylbhefrys pbpnvar cbea wnpxnff qhzonff nffung nffjvcr')
_WEAK = ('shx shd spx sipx cuhpx fulg fuvvg avtre avtn snt sntf qlxr encr encvfg anmv phz gvgf obbof obbo qvpx pbpx phag nahf nany frk frkl '
         'ahqr anxrq xxx crqb xlf pbba wvunq penc nff nefr cvff gneq urebva xvxr puvax tbbx fcvp jrgonpx ornare ubzb')
_ALLOW = 'chfflpng chffljvyybj'
ENDINGS = ('', 's', 'es', 'y', 'ed', 'er', 'ers', 'ing', 'head', 'face', 'hat', 'hole')

BLOCKED_FILE = os.environ.get('OT_BLOCKED_NAMES_FILE', '/ot/data/blocked_names.txt')
DB_FOLDER = os.environ.get('OT_ASTRONDB', 'astron/databases/astrondb')
MIN_LENGTH, MAX_LENGTH, MAX_WORDS = 2, 24, 4

LOOKALIKE = {ord('0'): 'o', ord('1'): 'i', ord('3'): 'e', ord('4'): 'a', ord('5'): 's', ord('7'): 't', ord('@'): 'a', ord('$'): 's', ord('!'): 'i'}
# letters of other alphabets that look like Latin letters
CONFUSABLES = {
    'а': 'a', 'е': 'e', 'о': 'o', 'р': 'p', 'с': 'c', 'х': 'x', 'у': 'y', 'і': 'i', 'ј': 'j',
    'ѕ': 's', 'һ': 'h', 'к': 'k', 'м': 'm', 'т': 't', 'н': 'h', 'в': 'b', 'ԁ': 'd', 'ԛ': 'q',
    'ο': 'o', 'α': 'a', 'ε': 'e', 'ι': 'i', 'ν': 'v', 'ρ': 'p', 'υ': 'u', 'κ': 'k', 'τ': 't',
    'χ': 'x', 'ı': 'i', 'ɡ': 'g', 'ƒ': 'f', 'ø': 'o', 'đ': 'd', 'ł': 'l', 'ħ': 'h', 'ŧ': 't', 'ᴀ': 'a', 'ᴄ': 'c', 'ᴇ': 'e', 'ɪ': 'i', 'ᴏ': 'o', 'ᴛ': 't',
}
_TRANSLATE = dict(LOOKALIKE)
_TRANSLATE.update({ord(k): v for k, v in CONFUSABLES.items()})

_blocked = {'mtime': None, 'checked': 0.0, 'lists': None}
_used = {'checked': 0.0, 'names': set()}
_npc = {'names': None}


def _evenOut(text):
    return re.sub(r'(.)\1+', r'\1', text)


def _flatten(text):
    """Lower case, accents and width variants removed, look-alike characters turned into letters. Not yet reduced to letters only."""
    text = unicodedata.normalize('NFKD', str(text).lower())
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.translate(_TRANSLATE)


def _squash(text):
    """The flattened text with only letters left and runs of the same letter shortened to one."""
    return _evenOut(''.join(c for c in _flatten(text) if c.isalpha()))


def _lists():
    """(strong words, weak words, allowed words), all squashed. Built in, plus the file when there is one."""
    now = time.time()
    if _blocked['lists'] is not None and now - _blocked['checked'] < 10.0:
        return _blocked['lists']
    _blocked['checked'] = now
    try:
        mtime = os.stat(BLOCKED_FILE).st_mtime
    except OSError:
        mtime = None
    if _blocked['lists'] is None or mtime != _blocked['mtime']:
        strong = set(codecs.decode(_STRONG, 'rot13').split())
        weak = set(codecs.decode(_WEAK, 'rot13').split())
        allow = set(codecs.decode(_ALLOW, 'rot13').split())
        if mtime is not None:
            try:
                with open(BLOCKED_FILE, encoding='utf8') as f:
                    for line in f:
                        w = line.strip().lower()
                        if not w or w.startswith('#'):
                            continue
                        if w.startswith('*'):
                            strong.add(w[1:])
                        elif w.startswith('!'):
                            allow.add(w[1:])
                        else:
                            weak.add(w)
            except OSError:
                pass
        _blocked['lists'] = (set(filter(None, map(_squash, strong))), set(filter(None, map(_squash, weak))), set(filter(None, map(_squash, allow))))
        _blocked['mtime'] = mtime
    return _blocked['lists']


def containsBlockedWord(name):
    strong, weak, allow = _lists()
    tokens = [_squash(t) for t in re.split(r"[\s\-'.,_]+", _flatten(name)) if t]
    tokens = [t for t in tokens if t and t not in allow]
    joined = ''.join(tokens)
    if any(word in joined for word in strong):
        return True
    forms = set(w + e for w in strong | weak for e in ENDINGS)
    return any(t in forms for t in tokens)


def _usedNames():
    """Every name already on a toon (and every name waiting on one), lower case. Read from the toon files, and kept for 20 seconds."""
    now = time.time()
    if now - _used['checked'] < 20.0:
        return _used['names']
    _used['checked'] = now
    names = set()
    try:
        for f in os.listdir(DB_FOLDER):
            if not f.endswith('.yaml'):
                continue
            with open(os.path.join(DB_FOLDER, f), encoding='utf8', errors='replace') as fh:
                text = fh.read()
            if 'class: DistributedToon' not in text:
                continue
            for m in re.finditer(r'^\s+(?:setName|WishName): \("(.*)"\)\s*$', text, re.M):
                if m.group(1):
                    names.add(m.group(1).strip().lower())
        _used['names'] = names
    except OSError:
        notify.warning('could not read the toon files to look for duplicate names')
    return _used['names']


def rememberName(name):
    _usedNames().add(name.strip().lower())


def _npcMatch(name):
    if _npc['names'] is None:
        from toontown.toon import NPCToons
        _npc['names'] = set(str(v[1]).strip().lower() for v in NPCToons.NPCToonDict.values())
    return name.strip().lower() in _npc['names']


def clean(name):
    return ' '.join(name.split())


def judge(name):
    """None when the name is fine, otherwise a short reason (for the server log; the player sees the game's standard message)."""
    if GameConfig.get('typed_names', 'auto') == 'off':
        return 'typed names are switched off'
    name = clean(name)
    if len(name) < MIN_LENGTH or len(name) > MAX_LENGTH:
        return 'length'
    if len(name.split()) > MAX_WORDS:
        return 'too many words'
    problem = NameCheck.checkName(name)
    if problem:
        return 'name rules: %s' % problem
    if _npcMatch(name):
        return 'same as an NPC'
    if containsBlockedWord(name):
        return 'blocked word'
    if name.lower() in _usedNames():
        return 'already taken'
    return None


def decide(name):
    """(the cleaned name, None or the reason it was rejected). Never raises: a bug in the checks counts as a rejection."""
    try:
        name = clean(name)
        problem = judge(name)
    except Exception:
        notify.warning('judging a typed name failed: ' + traceback.format_exc())
        return clean(str(name)), 'internal error'
    if problem:
        notify.info('typed name rejected (%s): %r' % (problem, name))
    return name, problem
