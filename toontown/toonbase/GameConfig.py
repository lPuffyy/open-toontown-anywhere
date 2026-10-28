"""Settings the person running the server can change without a rebuild.

They live in one small file, gameconfig.json, in the server's data folder (/ot/data/gameconfig.json), for example
{"gag_xp_boost": 4}. The server looks at the file again whenever it changes (checked every few seconds), so a new value reaches the
next battle. The browser game gets the same file from the web server (/gameconfig.json) when the page starts the game, so players
pick up a change the next time they load the page. Anything missing falls back to the default written in the code.

The web server serves this file to everyone, so keep secrets out of it.
"""
import json
import os
import sys
import time

DEFAULT_FILE = '/ot/data/gameconfig.json'
RECHECK_SECONDS = 5.0

_server = {'checked': 0.0, 'mtime': None, 'data': {}}
_browser = {'data': None}


def _isNumber(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _serverData():
    now = time.time()
    if now - _server['checked'] < RECHECK_SECONDS:
        return _server['data']
    _server['checked'] = now
    path = os.environ.get('OT_GAMECONFIG_FILE', DEFAULT_FILE)
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        _server['mtime'] = None
        _server['data'] = {}                  # no file: every setting is back to its default
        return _server['data']
    if mtime != _server['mtime']:
        try:
            with open(path) as f:
                data = json.load(f)
            _server['data'] = data if isinstance(data, dict) else {}
            _server['mtime'] = mtime
        except (OSError, ValueError):
            pass                              # half-written or invalid: keep the last good settings
    return _server['data']


def _browserData():
    if _browser['data'] is None:
        try:
            import platform
            text = str(platform.window.ttr.gameConfig or '')     # the page fetched gameconfig.json before it started the game
        except Exception:
            text = os.environ.get('OT_GAMECONFIG') or ''
        try:
            data = json.loads(text or '{}')
        except ValueError:
            data = {}
        _browser['data'] = data if isinstance(data, dict) else {}
    return _browser['data']


def get(key, default):
    """The setting called key, or default when it is missing or is not a sensible value (a number must be 0 or more)."""
    data = _browserData() if sys.platform == 'emscripten' else _serverData()
    value = data.get(key)
    if _isNumber(default):
        return value if _isNumber(value) and value >= 0 else default
    return default if value is None else value
