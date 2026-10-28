"""Judges a name a player typed when making a toon, so the server can approve typed names itself.

The checks, in order:
  1. typed names switched off in gameconfig.json ("typed_names": "off")  -> rejected
  2. size: 2 to 24 characters, at most 4 words
  3. the game's own name rules (otp.namepanel.NameCheck: characters, capitals, vowels, punctuation) and no match with an NPC's name
  4. blocked words (below)
  5. not the same as a name another toon already has

The blocked words are a STARTER list. It is kept ROT13-encoded so the repository does not spell the words out, and it is extended by an
optional file, /ot/data/blocked_names.txt (one word per line, "#" starts a comment; read again when the file changes). Short words (4 letters
or fewer) only count as a whole word; longer ones also count inside a longer run of letters. Look-alike characters (0 for o, 1 for i, 3 for e,
4 for a, 5 for s, 7 for t, @ for a, $ for s) and repeated letters are evened out first. A filter like this stops the obvious cases; it cannot
stop every determined player, so extend the file as you see names you do not want.
"""
import codecs
import os
import re
import time

from direct.directnotify import DirectNotifyGlobal

from otp.namepanel import NameCheck
from toontown.toonbase import GameConfig

notify = DirectNotifyGlobal.directNotify.newCategory('NameJudge')

_SEED = ('shpx shx shd fuvg fuvggl ovgpu phag qvpx pbpx chffl nffubyr onfgneq juber fyhg avttre avttn avtre snttbg snt ergneq ergneqrq '
         'encr encvfg anmv uvgyre cbea cravf intvan nahf phz wvmm gvgf obbof obbo qvyqb zbyrfg crqb crqbcuvyr xxx')
BLOCKED_FILE = os.environ.get('OT_BLOCKED_NAMES_FILE', '/ot/data/blocked_names.txt')
DB_FOLDER = os.environ.get('OT_ASTRONDB', 'astron/databases/astrondb')
MIN_LENGTH, MAX_LENGTH, MAX_WORDS = 2, 24, 4
LOOKALIKE = {ord('0'): 'o', ord('1'): 'i', ord('3'): 'e', ord('4'): 'a', ord('5'): 's', ord('7'): 't', ord('@'): 'a', ord('$'): 's', ord('!'): 'i'}

_blocked = {'mtime': None, 'checked': 0.0, 'words': None}
_used = {'checked': 0.0, 'names': set()}
_npc = {'names': None}


def _evenOut(text):
    return re.sub(r'(.)\1+', r'\1', text)


def _blockedWords():
    now = time.time()
    if _blocked['words'] is not None and now - _blocked['checked'] < 10.0:
        return _blocked['words']
    _blocked['checked'] = now
    try:
        mtime = os.stat(BLOCKED_FILE).st_mtime
    except OSError:
        mtime = None
    if _blocked['words'] is None or mtime != _blocked['mtime']:
        words = set(codecs.decode(_SEED, 'rot13').split())
        if mtime is not None:
            try:
                with open(BLOCKED_FILE, encoding='utf8') as f:
                    words |= set(w.strip().lower() for w in f if w.strip() and not w.startswith('#'))
            except OSError:
                pass
        _blocked['words'] = set(_evenOut(w) for w in words)
        _blocked['mtime'] = mtime
    return _blocked['words']


def _squash(text):
    """lower case, look-alikes turned into letters, only letters kept, runs of the same letter shortened to one"""
    text = text.lower().translate(LOOKALIKE)
    return _evenOut(''.join(c for c in text if c.isalpha()))


def containsBlockedWord(name):
    tokens = [_squash(t) for t in re.split(r"[\s\-'.,]+", name) if t]
    joined = ''.join(tokens)
    for word in _blockedWords():
        if word in tokens:
            return True
        if len(word) >= 5 and word in joined:
            return True
    return False


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
