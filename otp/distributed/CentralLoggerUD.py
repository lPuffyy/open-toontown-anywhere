import json
import os
import time
import traceback

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalUD import DistributedObjectGlobalUD


class CentralLoggerUD(DistributedObjectGlobalUD):
    """Receives the Report button on a toon's panel and keeps each report for the moderator panel (docker/auth_service.py),
    one JSON line per report in REPORTS_FILE. Other client events are only logged."""
    notify = DirectNotifyGlobal.directNotify.newCategory('CentralLoggerUD')
    REPORTS_FILE = '/ot/data/mod/reports.jsonl'
    MAX_PER_HOUR = 15               # reports one toon can send in an hour
    CATEGORIES = {'MODERATION_FOUL_LANGUAGE': 'Foul language', 'MODERATION_PERSONAL_INFO': 'Personal info',
                  'MODERATION_RUDE_BEHAVIOR': 'Rude or mean', 'MODERATION_BAD_NAME': 'Bad name', 'MODERATION_HACKING': 'Hacking'}

    def __init__(self, air):
        DistributedObjectGlobalUD.__init__(self, air)
        self.sent = {}              # reporter avId -> times of its reports in the last hour

    def sendMessage(self, category, eventString, targetDISLId, targetAvId):
        reporter = self.air.getAvatarIdFromSender()
        if eventString != 'REPORT_PLAYER':
            self.notify.debug('client event from %s: %s %s' % (reporter, category, eventString[:200]))
            return
        if not reporter or not targetAvId or reporter == targetAvId or category not in self.CATEGORIES:
            return
        now = time.time()
        times = [t for t in self.sent.get(reporter, []) if now - t < 3600]
        if len(times) >= self.MAX_PER_HOUR:
            self.notify.warning('toon %s sent too many reports; ignoring' % reporter)
            return
        times.append(now)
        self.sent[reporter] = times
        presence = getattr(self.air, 'toonPresence', None)
        district = getattr(presence, 'district', {}) if presence else {}
        report = {'id': '%d-%d' % (int(now * 1000), reporter), 'time': int(now), 'category': self.CATEGORIES[category],
                  'reporter': reporter, 'target': targetAvId, 'district': district.get(targetAvId) or district.get(reporter) or ''}
        self.notify.info('toon %s reported toon %s: %s' % (reporter, targetAvId, report['category']))
        names = {}

        def write():
            report['reporterName'] = names.get(reporter, '')
            report['targetName'] = names.get(targetAvId, '')
            try:
                os.makedirs(os.path.dirname(self.REPORTS_FILE), exist_ok=True)
                with open(self.REPORTS_FILE, 'a', encoding='utf8') as f:
                    f.write(json.dumps(report) + '\n')
            except Exception:
                self.notify.warning('could not save a report: %s' % traceback.format_exc())

        def lookup(avIds):
            if not avIds:
                return write()
            avId = avIds[0]

            def got(dclass, fields):
                try:
                    if fields and fields.get('setName'):
                        names[avId] = fields['setName'][0]
                except Exception:
                    pass
                lookup(avIds[1:])
            try:
                self.air.dbInterface.queryObject(self.air.dbId, avId, got)
            except Exception:
                lookup(avIds[1:])
        lookup([reporter, targetAvId])
