import json
import os
import sys


class Settings:
    """The player's options (music, sound effects, and so on). On a computer they are a file next to the game. In the browser
    the game's files vanish when the page is closed, so they are kept in the browser's own storage instead, one set for each
    sign-in name, and come back the next time the same name plays on that phone."""

    def __init__(self):
        self.__settings = {}
        self.__filename = 'useropt.json'
        self.__storage = None
        self.__storageKey = None
        if sys.platform == 'emscripten':
            try:
                import platform
                self.__storage = platform.window.localStorage
                self.__storageKey = 'ttr_options_' + os.environ.get('LOGIN_TOKEN', 'player')
            except Exception:
                self.__storage = None

    def __stored(self):
        try:
            value = self.__storage.getItem(self.__storageKey)
            return str(value) if value is not None else None
        except Exception:
            return None

    def doSavedSettingsExist(self):
        if self.__storage is not None:
            return self.__stored() is not None
        return os.path.exists(self.__filename)

    def readSettings(self):
        if not self.doSavedSettingsExist():
            self.__settings = {}
            return

        try:
            if self.__storage is not None:
                self.__settings = json.loads(self.__stored())
            else:
                with open(self.__filename, 'r') as f:
                    self.__settings = json.load(f)
        except:
            self.__settings = {}

    def writeSettings(self):
        if self.__storage is not None:
            try:
                self.__storage.setItem(self.__storageKey, json.dumps(self.__settings))
            except Exception:
                pass
            return
        with open(self.__filename, 'w+') as f:
            json.dump(self.__settings, f, indent=4)

    def updateSetting(self, setting, value):
        self.__settings[setting] = value

    def getSetting(self, setting, default=None):
        return self.__settings.get(setting, default)
