# Copyright (C) 2007 AG-Projects.
#

"""Implementation of an OpenSER backend."""

import time
from StringIO import StringIO
from lxml import etree

from twisted.enterprise import adbapi, util as dbutil
from twisted.internet import defer

from application.configuration import readSettings, ConfigSection
from application import log

from xcap.interfaces.backend import database
from xcap.interfaces.openser import ManagementInterface
from xcap.errors import ResourceNotFound

class OpenSERConfig(ConfigSection):
    authentication_db_uri = 'mysql://user:pass@db/openser'
    storage_db_uri = 'mysql://user:pass@db/openser'
    xmlrpc_url = 'http://localhost:8080'

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('OpenSER', OpenSERConfig)

class PlainPasswordChecker(database.PlainPasswordChecker):
    db_uri = OpenSERConfig.authentication_db_uri
class HashPasswordChecked(database.HashPasswordChecker):
    db_uri = OpenSERConfig.authentication_db_uri

class Storage(database.Storage):
    
    db_uri = OpenSERConfig.storage_db_uri

    def __init__(self):
        database.Storage.__init__(self)
        self._mi = ManagementInterface(OpenSERConfig.xmlrpc_url)

    def _notify_watchers(self, response, user_id):
        def _eb_mi(f):
            log.error("Error while notifying OpenSER management interface for 'user' %s: %s" % (user_id, f.getErrorMessage()))
            return response
        d = self._mi.notify_watchers('%s@%s' % (user_id.username, user_id.domain))
        d.addCallback(lambda x: response)
        d.addErrback(_eb_mi)
        return d

    def put_document(self, uri, document, check_etag):
        application_id = uri.application_id
        d = self.conn.runInteraction(super(Storage, self)._put_document, uri, document, check_etag)        
        if application_id in ('pres-rules', 'org.openmobilealliance.pres-rules', 'pidf-manipulation'):
            ## signal OpenSER of the modification through the management interface
            d.addCallback(self._notify_watchers, uri.user)
        return d
