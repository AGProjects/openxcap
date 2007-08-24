# Copyright (C) 2007 AG-Projects.
#

"""Implementation of a database storage"""

import md5
import time

from application.python.util import Singleton
from application.configuration import readSettings, ConfigSection

from zope.interface import implements
from twisted.enterprise import adbapi, util as dbutil
from twisted.internet import defer

from xcap.interfaces.storage import IStorage, StatusResponse
from xcap.errors import ResourceNotFound
from xcap.dbutil import connectionForURI


class StorageConfig(ConfigSection):
    db_uri = 'mysql://user:pass@db/openser'

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('Storage', StorageConfig)

class Storage(object):
    __metaclass__ = Singleton
    
    implements(IStorage)

    app_mapping = {"pres-rules"       : 2,
                   "org.openmobilealliance.pres-rules": 2,
                   "resource-lists"   : 4,
                   "rls-services"     : 8,
                   "pidf-manipulation": 16}

    def __init__(self):
        self.__db_connect()

    def __db_connect(self):
        self.conn = connectionForURI(StorageConfig.db_uri)

    def _get_document(self, trans, uri, check_etag):
        username, domain = uri.user.username, uri.user.domain
        doc_type = self.app_mapping[uri.application_id]
        quote = dbutil.quote
        query = """SELECT xcap, etag FROM xcap_xml
                   WHERE username = %(username)s AND domain = %(domain)s
                   AND doc_type= %(doc_type)s""" % {
                       "username": quote(username, "char"),
                       "domain"  : quote(domain, "char"),
                       "doc_type": quote(doc_type, "int")}
        trans.execute(query)
        result = trans.fetchall()
        if result:
            doc, etag = result[0]
            check_etag(etag)
            response = StatusResponse(200, etag, doc)
        else:
            response = StatusResponse(404)
        return response

    def _put_document(self, trans, uri, document, check_etag):
        username, domain = uri.user.username, uri.user.domain
        doc_type = self.app_mapping[uri.application_id]
        quote = dbutil.quote
        query = """SELECT etag FROM xcap_xml
                   WHERE username = %(username)s AND domain = %(domain)s
                   AND doc_type= %(doc_type)s""" % {
                       "username": quote(username, "char"),
                       "domain"  : quote(domain, "char"),
                       "doc_type": quote(doc_type, "int")}
        trans.execute(query)
        result = trans.fetchall()
        if not result:
            ## the document doesn't exist, create it
            etag = self.generate_etag(uri, document)
            query = """INSERT INTO xcap_xml
                       (username, domain, doc_type, etag, xcap) 
                       VALUES (%(username)s, %(domain)s, %(doc_type)s, %(etag)s, %(document)s)""" % {
                           "username": quote(username, "char"),
                           "domain"  : quote(domain, "char"),
                           "doc_type": quote(doc_type, "int"),
                           "etag":     quote(etag, "char"),
                           "document": quote(document, "char")}
            trans.execute(query)
            return StatusResponse(201, etag)
        else:
            old_etag = result[0][0]
            ## first check the etag of the existing resource
            check_etag(old_etag)
            ## the document exists, replace it
            etag = self.generate_etag(uri, document)
            query = """UPDATE xcap_xml
                       SET xcap = %(document)s, etag = %(etag)s
                       WHERE username = %(username)s AND domain = %(domain)s
                       AND doc_type = %(doc_type)s AND etag = %(old_etag)s""" % {
                           "document": quote(document, "char"),
                           "etag":     quote(etag, "char"),
                           "username": quote(username, "char"),
                           "domain"  : quote(domain, "char"),
                           "doc_type": quote(doc_type, "int"),
                           "old_etag": quote(old_etag, "char")}
            trans.execute(query)
            ## verifica daca update a modificat vreo coloana, daca nu arunca eroare
            return StatusResponse(200, etag)

    def _delete_document(self, trans, uri, check_etag):
        username, domain = uri.user.username, uri.user.domain
        doc_type = self.app_mapping[uri.application_id]
        quote = dbutil.quote
        query = """SELECT etag FROM xcap_xml
                   WHERE username = %(username)s AND domain = %(domain)s
                   AND doc_type= %(doc_type)s""" % {
                       "username": quote(username, "char"),
                       "domain"  : quote(domain, "char"),
                       "doc_type": quote(doc_type, "int")}
        trans.execute(query)
        result = trans.fetchall()
        if result:
            etag = result[0][0]
            check_etag(etag)
            query = """DELETE FROM xcap_xml
                       WHERE username = %(username)s AND domain = %(domain)s
                       AND doc_type= %(doc_type)s""" % {
                           "username": quote(username, "char"),
                           "domain"  : quote(domain, "char"),
                           "doc_type": quote(doc_type, "int")}
            trans.execute(query)
            return StatusResponse(200, etag)
        else:
            return StatusResponse(404)

    def get_document(self, uri, check_etag):
        return self.conn.runInteraction(self._get_document, uri, check_etag)

    def put_document(self, uri, document, check_etag):
        return self.conn.runInteraction(self._put_document, uri, document, check_etag)

    def delete_document(self, uri, check_etag):
        return self.conn.runInteraction(self._delete_document, uri, check_etag)

    def generate_etag(self, uri, document):
        return md5.new(uri.xcap_root + str(uri.doc_selector) + str(time.time())).hexdigest()
