
# Copyright (C) 2007-2010 AG-Projects.
#

"""Implementation of an OpenSIPS backend."""

import sys
from application import log
from application.configuration import ConfigSection, ConfigSetting

import xcap
from xcap.datatypes import XCAPRootURI
from xcap.interfaces.backend import database
from xcap.interfaces.opensips import ManagementInterface
from xcap.xcapdiff import Notifier


class ServerConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Server'

    root = ConfigSetting(type=XCAPRootURI, value=None)


class Config(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'OpenSIPS'

    xmlrpc_url = ConfigSetting(type=str, value=None)
    enable_publish_xcapdiff = False

if Config.xmlrpc_url is None:
    log.fatal("the OpenSIPS.xmlrpc_url option is not set")
    sys.exit(1)

class PlainPasswordChecker(database.PlainPasswordChecker): pass
class HashPasswordChecker(database.HashPasswordChecker): pass

class BaseStorage(database.Storage):

    def __init__(self):
        database.Storage.__init__(self)
        self._mi = ManagementInterface(Config.xmlrpc_url)

    def _notify_watchers(self, response, user_id, event, type):
        def _eb_mi(f):
            log.error("Error while notifying OpenSIPS management interface for user %s: %s" % (user_id, f.getErrorMessage()))
            return response
        d = self._mi.notify_watchers('%s@%s' % (user_id.username, user_id.domain), event, type)
        d.addCallback(lambda x: response)
        d.addErrback(_eb_mi)
        return d

    def put_document(self, uri, document, check_etag):
        application_id = uri.application_id
        d = self.conn.runInteraction(super(BaseStorage, self)._put_document, uri, document, check_etag)
        if application_id in ('pres-rules', 'org.openmobilealliance.pres-rules', 'pidf-manipulation', 'org.openxcap.dialog-rules', 'resource-lists', 'rls-services'):
            type = 1 if application_id == 'pidf-manipulation' else 0
            event = 'dialog' if application_id == 'org.openxcap.dialog-rules' else 'presence'
            d.addCallback(self._notify_watchers, uri.user, event, type)
        return d

class NotifyingStorage(BaseStorage):

    def __init__(self):
        BaseStorage.__init__(self)
        self.notifier = Notifier(ServerConfig.root, self._mi.publish_xcapdiff)

    def put_document(self, uri, document, check_etag):
        d = super(NotifyingStorage, self).put_document(uri, document, check_etag)
        d.addCallback(lambda result: self._on_put(result, uri))
        return d

    def delete_document(self, uri, check_etag):
        d = super(NotifyingStorage, self).delete_document(uri, check_etag)
        d.addCallback(lambda result: self._on_delete(result, uri))
        return d

    def _on_put(self, result, uri):
        if result.succeed:
            self.notifier.on_change(uri, result.old_etag, result.etag)
        return result

    def _on_delete(self, result, uri):
        if result.succeed:
            self.notifier.on_change(uri, result.old_etag, None)
        return result


if Config.enable_publish_xcapdiff:
    Storage = NotifyingStorage
else:
    Storage = BaseStorage

installSignalHandlers = database.installSignalHandlers
