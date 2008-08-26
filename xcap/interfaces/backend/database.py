# Copyright (C) 2007 AG-Projects.
#

"""Implementation of a database backend."""

import md5
import time

from application.configuration import *
from application.python.util import Singleton

from zope.interface import implements
from twisted.cred import credentials, portal, checkers, error as credError
from twisted.internet import defer
from twisted.enterprise import adbapi, util as dbutil

from xcap.interfaces.backend import IStorage, StatusResponse
from xcap.errors import ResourceNotFound
from xcap.dbutil import connectionForURI


class Config(ConfigSection):
    authentication_db_uri = 'mysql://user:pass@db/openser'
    storage_db_uri = 'mysql://user:pass@db/openser'
    subscriber_table = 'subscriber'
    user_col = 'username'
    domain_col = 'domain'
    password_col = 'password'
    ha1_col = 'ha1'
    xcap_table = 'xcap'

## We use this to overwrite some of the settings above on a local basis if needed
configuration = ConfigFile('config.ini')
configuration.read_settings('Database', Config)

class PasswordChecker:
    """A credentials checker against a database subscriber table."""

    implements(checkers.ICredentialsChecker)

    credentialInterfaces = (credentials.IUsernamePassword,
        credentials.IUsernameHashedPassword)

    def __init__(self):
        self.__db_connect()

    def __db_connect(self):
        self.conn = connectionForURI(Config.authentication_db_uri)

    def _query_credentials(self, credentials):
        raise NotImplementedError

    def _got_query_results(self, rows, credentials):
        if not rows:
            raise credError.UnauthorizedLogin("Unauthorized login")
        else:
            return self._authenticate_credentials(rows[0][0], credentials)

    def _authenticate_credentials(self, password, credentials):
        raise NotImplementedError

    def _checkedPassword(self, matched, username, realm):
        if matched:
            username = username.split('@', 1)[0]
            ## this is the avatar ID
            return "%s@%s" % (username, realm)
        else:
            raise credError.UnauthorizedLogin("Unauthorized login")

    def requestAvatarId(self, credentials):
        """Return the avatar ID for the credentials which must have the username 
           and realm attributes, or an UnauthorizedLogin in case of a failure."""
        d = self._query_credentials(credentials)
        return d


class PlainPasswordChecker(PasswordChecker):
    """A credentials checker against a database subscriber table, where the passwords
       are stored in plain text."""

    implements(checkers.ICredentialsChecker)

    def _query_credentials(self, credentials):
        username, domain = credentials.username.split('@', 1)[0], credentials.realm
        quote = dbutil.quote
        query = """SELECT %(password_col)s
                   FROM %(table)s
                   WHERE %(user_col)s = %(username)s
                   AND %(domain_col)s = %(domain)s""" % {
                    "password_col": Config.password_col,
                    "user_col": Config.user_col,
                    "domain_col": Config.domain_col,
                    "table":    Config.subscriber_table,
                    "username": quote(username, "char"),
                    "domain":   quote(domain, "char")}
        return self.conn.runQuery(query).addCallback(self._got_query_results, credentials)

    def _authenticate_credentials(self, hash, credentials):
        return defer.maybeDeferred(
                credentials.checkPassword, hash).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)


class HashPasswordChecker(PasswordChecker):
    """A credentials checker against a database subscriber table, where the passwords
       are stored as MD5 hashes."""

    implements(checkers.ICredentialsChecker)

    def _query_credentials(self, credentials):
        username, domain = credentials.username.split('@', 1)[0], credentials.realm
        quote = dbutil.quote
        query = """SELECT %(ha1_col)s
                   FROM %(table)s
                   WHERE %(user_col)s = %(username)s
                   AND %(domain_col)s = %(domain)s""" % {
                    "ha1_col":  Config.ha1_col,
                    "user_col": Config.user_col,
                    "domain_col": Config.domain_col,
                    "table":    Config.subscriber_table,
                    "username": quote(username, "char"),
                    "domain":   quote(domain, "char")}
        return self.conn.runQuery(query).addCallback(self._got_query_results, credentials)

    def _authenticate_credentials(self, hash, credentials):
        return defer.maybeDeferred(
                credentials.checkHash, hash).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)


class Storage(object):
    __metaclass__ = Singleton
    
    implements(IStorage)

    app_mapping = {"pres-rules"       : 1<<1,
                   "org.openmobilealliance.pres-rules": 1<<1,
                   "resource-lists"   : 1<<2,
                   "rls-services"     : 1<<3,
                   "pidf-manipulation": 1<<4,
                   "test-app"         : 0}

    def __init__(self):
        self.__db_connect()

    def __db_connect(self):
        self.conn = connectionForURI(Config.storage_db_uri)

    def _normalize_document_path(self, uri):
        ## some clients e.g. counterpath's eyebeam save presence rules under
        ## different filenames between versions and they expect to find the same
        ## information, thus we are forcing all presence rules documents to be
        ## saved under "index.xml" default filename
        if uri.application_id in ("org.openmobilealliance.pres-rules", "pres-rules"):
            uri.doc_selector.document_path = "index.xml"

    def _get_document(self, trans, uri, check_etag):
        username, domain = uri.user.username, uri.user.domain
        self._normalize_document_path(uri)
        doc_type = self.app_mapping[uri.application_id]
        quote = dbutil.quote
        query = """SELECT doc, etag FROM %(table)s
                   WHERE username = %(username)s AND domain = %(domain)s
                   AND doc_type= %(doc_type)s AND doc_uri=%(document_path)s""" % {
                       "table":    Config.xcap_table,
                       "username": quote(username, "char"),
                       "domain"  : quote(domain, "char"),
                       "doc_type": quote(doc_type, "int"),
                       "document_path": quote(uri.doc_selector.document_path, "char")}
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
        self._normalize_document_path(uri)
        doc_type = self.app_mapping[uri.application_id]
        document_path = uri.doc_selector.document_path
        quote = dbutil.quote
        query = """SELECT etag FROM %(table)s
                   WHERE username = %(username)s AND domain = %(domain)s
                   AND doc_type= %(doc_type)s AND doc_uri=%(document_path)s""" % {
                       "table":    Config.xcap_table,
                       "username": quote(username, "char"),
                       "domain"  : quote(domain, "char"),
                       "doc_type": quote(doc_type, "int"),
                       "document_path": quote(document_path, "char")}
        trans.execute(query)
        result = trans.fetchall()
        if not result:
            ## the document doesn't exist, create it
            etag = self.generate_etag(uri, document)
            query = """INSERT INTO %(table)s
                       (username, domain, doc_type, etag, doc, doc_uri)
                       VALUES (%(username)s, %(domain)s, %(doc_type)s, %(etag)s, %(document)s, %(document_path)s)""" % {
                           "table":    Config.xcap_table,
                           "username": quote(username, "char"),
                           "domain"  : quote(domain, "char"),
                           "doc_type": quote(doc_type, "int"),
                           "etag":     quote(etag, "char"),
                           "document": quote(document, "char"),
                           "document_path": quote(document_path, "char")}
            trans.execute(query)
            return StatusResponse(201, etag)
        else:
            old_etag = result[0][0]
            ## first check the etag of the existing resource
            check_etag(old_etag)
            ## the document exists, replace it
            etag = self.generate_etag(uri, document)
            query = """UPDATE %(table)s
                       SET doc = %(document)s, etag = %(etag)s
                       WHERE username = %(username)s AND domain = %(domain)s
                       AND doc_type = %(doc_type)s AND etag = %(old_etag)s
                       AND doc_uri = %(document_path)s""" % {
                           "table":    Config.xcap_table,
                           "document": quote(document, "char"),
                           "etag":     quote(etag, "char"),
                           "username": quote(username, "char"),
                           "domain"  : quote(domain, "char"),
                           "doc_type": quote(doc_type, "int"),
                           "old_etag": quote(old_etag, "char"),
                           "document_path": quote(document_path, "char")}
            trans.execute(query)
            ## verifica daca update a modificat vreo coloana, daca nu arunca eroare
            return StatusResponse(200, etag, old_etag=old_etag)

    def _delete_document(self, trans, uri, check_etag):
        username, domain = uri.user.username, uri.user.domain
        self._normalize_document_path(uri)
        doc_type = self.app_mapping[uri.application_id]
        document_path = uri.doc_selector.document_path
        quote = dbutil.quote
        query = """SELECT etag FROM %(table)s
                   WHERE username = %(username)s AND domain = %(domain)s
                   AND doc_type= %(doc_type)s AND doc_uri = %(document_path)s""" % {
                       "table":    Config.xcap_table,
                       "username": quote(username, "char"),
                       "domain"  : quote(domain, "char"),
                       "doc_type": quote(doc_type, "int"),
                       "document_path": quote(document_path, "char")}
        trans.execute(query)
        result = trans.fetchall()
        if result:
            etag = result[0][0]
            check_etag(etag)
            query = """DELETE FROM %(table)s
                       WHERE username = %(username)s AND domain = %(domain)s
                       AND doc_type= %(doc_type)s AND doc_uri = %(document_path)s""" % {
                           "table":    Config.xcap_table,
                           "username": quote(username, "char"),
                           "domain"  : quote(domain, "char"),
                           "doc_type": quote(doc_type, "int"),
                           "document_path": quote(document_path, "char")}
            trans.execute(query)
            return StatusResponse(200, old_etag=etag)
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

    def _get_watchers(self, trans, uri):
        status_mapping = {1: "allow",
                          2: "confirm",
                          3: "deny"}
        presentity_uri = "sip:%s@%s" % (uri.user.username, uri.user.domain)
        quote = dbutil.quote
        query = """SELECT watcher_username, watcher_domain, status FROM watchers
                   WHERE presentity_uri = %s""" % quote(presentity_uri, "char")
        trans.execute(query)
        result = trans.fetchall()
        watchers = [{"id": "%s@%s" % (w_user, w_domain),
                     "status": status_mapping.get(subs_status, "unknown"),
                     "online": "false"} for w_user, w_domain, subs_status in result]
        query = """SELECT watcher_username, watcher_domain FROM active_watchers
                   WHERE presentity_uri = %s AND event = 'presence'""" % quote(presentity_uri, "char")
        trans.execute(query)
        result = trans.fetchall()
        active_watchers = set("%s@%s" % pair for pair in result)
        for watcher in watchers:
            if watcher["id"] in active_watchers:
                watcher["online"] = "true"
        return watchers

    def get_watchers(self, uri):
        return self.conn.runInteraction(self._get_watchers, uri)

installSignalHandlers = True
