# Copyright (C) 2007 AG-Projects.
#

"""Implementation of an OpenSIPS backend."""

from application import log

from xcap.config import ConfigFile, ConfigSection
from xcap.interfaces.backend import database
from xcap.interfaces.opensips import ManagementInterface
from xcap.xcapdiff import Notifier
from xcap.root_uris import root_uris

class Config(ConfigSection):
    xmlrpc_url = None
    enable_publish_xcapdiff = False

configuration = ConfigFile()
configuration.read_settings('OpenSIPS', Config)

assert Config.xmlrpc_url, 'Option xmlrpc_url in section [OpenSIPS] must be set for opensips backend to run'

class PlainPasswordChecker(database.PlainPasswordChecker): pass
class HashPasswordChecker(database.HashPasswordChecker): pass

class BaseStorage(database.Storage):

    def __init__(self):
        database.Storage.__init__(self)
        self._mi = ManagementInterface(Config.xmlrpc_url)

    def _notify_watchers(self, response, user_id, type):
        def _eb_mi(f):
            log.error("Error while notifying OpenSIPS management interface for user %s: %s" % (user_id, f.getErrorMessage()))
            return response
        d = self._mi.notify_watchers('%s@%s' % (user_id.username, user_id.domain), type)
        d.addCallback(lambda x: response)
        d.addErrback(_eb_mi)
        return d

    def put_document(self, uri, document, check_etag):
        application_id = uri.application_id
        d = self.conn.runInteraction(super(BaseStorage, self)._put_document, uri, document, check_etag)
        if application_id in ('pres-rules', 'org.openmobilealliance.pres-rules', 'pidf-manipulation'):
            ## signal OpenSIPS of the modification through the management interface
            if application_id == 'pidf-manipulation':
                type = 1
            else:
                type = 0
            d.addCallback(self._notify_watchers, uri.user, type)
        return d

class NotifyingStorage(BaseStorage):

    def __init__(self):
        BaseStorage.__init__(self)
        self.notifier = Notifier(root_uris[0], self._mi.publish_xcapdiff)

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
