# Copyright (C) 2007 AG-Projects.
#

"""Implementation of an OpenSER backend."""

import time

from twisted.enterprise import adbapi, util as dbutil
from twisted.internet import defer

from application.configuration import *
from application import log

from xcap.interfaces.backend import database
from xcap.interfaces.openser import ManagementInterface
from xcap.errors import ResourceNotFound

class Config(ConfigSection):
    authentication_db_uri = 'mysql://user:pass@db/openser'
    storage_db_uri = 'mysql://user:pass@db/openser'
    subscriber_table = 'subscriber'
    user_col = 'username'
    domain_col = 'domain'
    password_col = 'password'
    ha1_col = 'ha1'
    xcap_table = 'xcap_xml'
    xmlrpc_url = 'http://localhost:8080'

## We use this to overwrite some of the settings above on a local basis if needed
configuration = ConfigFile('config.ini')
configuration.read_settings('OpenSER', Config)

class PlainPasswordChecker(database.PlainPasswordChecker): pass
class HashPasswordChecker(database.HashPasswordChecker): pass

class Storage(database.Storage):

    def __init__(self):
        database.Storage.__init__(self)
        self._mi = ManagementInterface(Config.xmlrpc_url)

    def _notify_watchers(self, response, user_id, type):
        def _eb_mi(f):
            log.error("Error while notifying OpenSER management interface for 'user' %s: %s" % (user_id, f.getErrorMessage()))
            return response
        d = self._mi.notify_watchers('%s@%s' % (user_id.username, user_id.domain), type)
        d.addCallback(lambda x: response)
        d.addErrback(_eb_mi)
        return d

    def put_document(self, uri, document, check_etag):
        application_id = uri.application_id
        d = self.conn.runInteraction(super(Storage, self)._put_document, uri, document, check_etag)        
        if application_id in ('pres-rules', 'org.openmobilealliance.pres-rules', 'pidf-manipulation'):
            ## signal OpenSER of the modification through the management interface
            if application_id == 'pidf-manipulation':
                type = 1
            else:
                type = 0
            d.addCallback(self._notify_watchers, uri.user, type)
        return d
