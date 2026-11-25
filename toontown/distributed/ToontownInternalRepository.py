from direct.directnotify import DirectNotifyGlobal
from otp.distributed.OTPInternalRepository import OTPInternalRepository
from otp.distributed.OtpDoGlobals import *

class ToontownInternalRepository(OTPInternalRepository):
    notify = DirectNotifyGlobal.directNotify.newCategory('ToontownInternalRepository')
    GameGlobalsId = OTP_DO_ID_TOONTOWN

    def __init__(self, baseChannel, serverId=None, dcFileNames=None, dcSuffix='AI', connectMethod=None, threadedNet=None):
        OTPInternalRepository.__init__(self, baseChannel, serverId, dcFileNames, dcSuffix, connectMethod, threadedNet)

    def handleDatagram(self, di):
        """One bad message (an error in some object's delete or update handler) must not take the whole district down:
        log it and carry on with the next message."""
        try:
            OTPInternalRepository.handleDatagram(self, di)
        except Exception:
            import traceback
            self.notify.warning('error while handling a message, ignored:\n%s' % traceback.format_exc())

    def _isValidPlayerLocation(self, parentId, zoneId):
        if zoneId < 1000 and zoneId != 1:
            return False

        return True
