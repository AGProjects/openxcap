
# Copyright (C) 2007-2010 AG-Projects.
#

"""Implementation of a database backend."""

import sys
from application import log
from application.configuration import ConfigSection
from application.python.util import Singleton

from zope.interface import implements
from twisted.cred import credentials, checkers, error as credError
from twisted.internet import defer

from _mysql_exceptions import IntegrityError

import xcap
from xcap.interfaces.backend import IStorage, StatusResponse
from xcap.dbutil import connectionForURI, repeat_on_error, make_random_etag

class Config(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Database'

    authentication_db_uri = ''
    storage_db_uri = ''
    subscriber_table = 'subscriber'
    user_col = 'username'
    domain_col = 'domain'
    password_col = 'password'
    ha1_col = 'ha1'
    xcap_table = 'xcap'

if not Config.authentication_db_uri or not Config.storage_db_uri:
    log.fatal("Authentication DB URI and Storage DB URI must be provided")
    sys.exit(1)


class DBBase(object):
    def __init__(self):
        self._db_connect()


class PasswordChecker(DBBase):
    """A credentials checker against a database subscriber table."""

    implements(checkers.ICredentialsChecker)

    credentialInterfaces = (credentials.IUsernamePassword,
        credentials.IUsernameHashedPassword)

    def _db_connect(self):
        self.conn = auth_db_connection(Config.authentication_db_uri)

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
        query = """SELECT %(password_col)s
                   FROM %(table)s
                   WHERE %(user_col)s = %%(username)s
                   AND %(domain_col)s = %%(domain)s""" % {
                    "password_col": Config.password_col,
                    "user_col": Config.user_col,
                    "domain_col": Config.domain_col,
                    "table":    Config.subscriber_table }
        params = {"username": username,
                  "domain":   domain}
        return self.conn.runQuery(query, params).addCallback(self._got_query_results, credentials)

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
        query = """SELECT %(ha1_col)s
                   FROM %(table)s
                   WHERE %(user_col)s = %%(username)s
                   AND %(domain_col)s = %%(domain)s""" % {
                    "ha1_col":  Config.ha1_col,
                    "user_col": Config.user_col,
                    "domain_col": Config.domain_col,
                    "table":    Config.subscriber_table}
        params = {"username": username,
                  "domain":   domain}
        return self.conn.runQuery(query, params).addCallback(self._got_query_results, credentials)

    def _authenticate_credentials(self, hash, credentials):
        return defer.maybeDeferred(
                credentials.checkHash, hash).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)

class Error(Exception):

    def __init__(self):
        if hasattr(self, 'msg'):
            return Exception.__init__(self, self.msg)
        else:
            return Exception.__init__(self)

class RaceError(Error):
    """The errors of this type are raised for the requests that failed because
    of concurrent modification of the database by other clients.

    For example, before DELETE we do SELECT first, to check that a document of the
    right etag exists. The actual check is performed by a function in twisted
    that is passed as a callback. Then etag from the SELECT request is used in the
    DELETE request.

    This seems unnecessary convoluted and probably should be changed to
    'DELETE .. WHERE etag=ETAG'. We still need to find out whether DELETE was
    actually performed.
    """

class UpdateFailed(RaceError):
    msg = 'UPDATE request failed'

class DeleteFailed(RaceError):
    msg = 'DELETE request failed'

class MultipleResultsError(Error):
    """This should never happen. If it did happen. that means either the table
    was corrupted or there's a logic error"""

    def __init__(self, params):
        Exception.__init__(self, 'database request has more than one result: ' + repr(params))

class Storage(DBBase):
    __metaclass__ = Singleton
    
    implements(IStorage)

    app_mapping = {"pres-rules"       : 1<<1,
                   "org.openmobilealliance.pres-rules": 1<<1,
                   "resource-lists"   : 1<<2,
                   "rls-services"     : 1<<3,
                   "pidf-manipulation": 1<<4,
                   "dialog-rules"     : 1<<5,
                   "icon"             : 1<<6,
                   "oma_status-icon"  : 1<<6,
                   "test-app"         : 0}

    def _db_connect(self):
        self.conn = storage_db_connection(Config.storage_db_uri)

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
        query = """SELECT doc, etag FROM %(table)s
                   WHERE username = %%(username)s AND domain = %%(domain)s
                   AND doc_type= %%(doc_type)s AND doc_uri=%%(document_path)s""" % {
            "table":    Config.xcap_table}
        params = {"username": username,
                  "domain"  : domain,
                  "doc_type": doc_type,
                  "document_path": uri.doc_selector.document_path}
        trans.execute(query, params)
        result = trans.fetchall()
        if len(result)>1:
            raise MultipleResultsError(params)
        elif result:
            doc, etag = result[0]
            if isinstance(doc, unicode):
                doc = doc.encode('utf-8')
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
        query = """SELECT etag FROM %(table)s
                   WHERE username = %%(username)s AND domain = %%(domain)s
                   AND doc_type= %%(doc_type)s AND doc_uri=%%(document_path)s""" % {
            "table":    Config.xcap_table}
        params = {"username": username,
                  "domain"  : domain,
                  "doc_type": doc_type,
                  "document_path": document_path}
        trans.execute(query, params)
        result = trans.fetchall()
        if len(result)>1:
            raise MultipleResultsError(params)
        elif not result:
            ## the document doesn't exist, create it
            etag = make_random_etag(uri)
            query = """INSERT INTO %(table)s (username, domain, doc_type, etag, doc, doc_uri)
 VALUES (%%(username)s, %%(domain)s, %%(doc_type)s, %%(etag)s, %%(document)s, %%(document_path)s)""" % {
                "table":    Config.xcap_table }
            params = {"username": username,
                      "domain"  : domain,
                      "doc_type": doc_type,
                      "etag":     etag,
                      "document": document,
                      "document_path": document_path}
            # may raise IntegrityError here, if the document was created in another connection
            # will be catched by repeat_on_error
            trans.execute(query, params)
            return StatusResponse(201, etag)
        else:
            old_etag = result[0][0]
            ## first check the etag of the existing resource
            check_etag(old_etag)
            ## the document exists, replace it
            etag = make_random_etag(uri)
            query = """UPDATE %(table)s
                       SET doc = %%(document)s, etag = %%(etag)s
                       WHERE username = %%(username)s AND domain = %%(domain)s
                       AND doc_type = %%(doc_type)s AND etag = %%(old_etag)s
                       AND doc_uri = %%(document_path)s""" % {
                "table":    Config.xcap_table }
            params = {"document": document,
                      "etag":     etag,
                      "username": username,
                      "domain"  : domain,
                      "doc_type": doc_type,
                      "old_etag": old_etag,
                      "document_path": document_path}
            trans.execute(query, params)
            # the request may not update anything (e.g. if etag was changed by another connection
            # after we did SELECT); if so, we should retry
            updated = getattr(trans._connection, 'affected_rows', lambda : 1)()
            if not updated:
                raise UpdateFailed
            assert updated == 1, updated
            return StatusResponse(200, etag, old_etag=old_etag)

    def _delete_document(self, trans, uri, check_etag):
        username, domain = uri.user.username, uri.user.domain
        self._normalize_document_path(uri)
        doc_type = self.app_mapping[uri.application_id]
        document_path = uri.doc_selector.document_path
        query = """SELECT etag FROM %(table)s
                   WHERE username = %%(username)s AND domain = %%(domain)s
                   AND doc_type= %%(doc_type)s AND doc_uri = %%(document_path)s""" % {
            "table":    Config.xcap_table}
        params = {"username": username,
                  "domain"  : domain,
                  "doc_type": doc_type,
                  "document_path": document_path}
        trans.execute(query, params)
        result = trans.fetchall()
        if len(result)>1:
            raise MultipleResultsError(params)
        elif result:
            etag = result[0][0]
            check_etag(etag)
            query = """DELETE FROM %(table)s
                       WHERE username = %%(username)s AND domain = %%(domain)s
                       AND doc_type= %%(doc_type)s AND doc_uri = %%(document_path)s
                       AND etag = %%(etag)s""" % {"table" : Config.xcap_table}
            params = {"username": username,
                      "domain"  : domain,
                      "doc_type": doc_type,
                      "document_path": document_path,
                      "etag": etag}
            trans.execute(query, params)
            deleted = getattr(trans._connection, 'affected_rows', lambda : 1)()
            if not deleted:
                # the document was replaced/removed after the SELECT but before the DELETE
                raise DeleteFailed
            assert deleted == 1, deleted
            return StatusResponse(200, old_etag=etag)
        else:
            return StatusResponse(404)

    def get_document(self, uri, check_etag):
        return self.conn.runInteraction(self._get_document, uri, check_etag)

    def put_document(self, uri, document, check_etag):
        return repeat_on_error(10, (UpdateFailed, IntegrityError),
                               self.conn.runInteraction, self._put_document, uri, document, check_etag)

    def delete_document(self, uri, check_etag):
        return repeat_on_error(10, DeleteFailed, self.conn.runInteraction, self._delete_document, uri, check_etag)

    # Application-specific functions
    def _get_watchers(self, trans, uri):
        status_mapping = {1: "allow",
                          2: "confirm",
                          3: "deny"}
        presentity_uri = "sip:%s@%s" % (uri.user.username, uri.user.domain)
        query = """SELECT watcher_username, watcher_domain, status FROM watchers
                   WHERE presentity_uri = %(puri)s"""
        params = {'puri': presentity_uri}
        trans.execute(query, params)
        result = trans.fetchall()
        watchers = [{"id": "%s@%s" % (w_user, w_domain),
                     "status": status_mapping.get(subs_status, "unknown"),
                     "online": "false"} for w_user, w_domain, subs_status in result]
        query = """SELECT watcher_username, watcher_domain FROM active_watchers
                   WHERE presentity_uri = %(puri)s AND event = 'presence'"""
        trans.execute(query, params)
        result = trans.fetchall()
        active_watchers = set("%s@%s" % pair for pair in result)
        for watcher in watchers:
            if watcher["id"] in active_watchers:
                watcher["online"] = "true"
        return watchers

    def get_watchers(self, uri):
        return self.conn.runInteraction(self._get_watchers, uri)

    def _get_documents_list(self, trans, uri):
        query = """SELECT doc_type, doc_uri, etag FROM %(table)s
                    WHERE username = %%(username)s AND domain = %%(domain)s""" % {'table': Config.xcap_table}
        params = {'username': uri.user.username, 'domain': uri.user.domain}
        trans.execute(query, params)
        result = trans.fetchall()
        docs = {}
        for r in result:
            app = [k for k, v in self.app_mapping.iteritems() if v == r[0]][0]
            if docs.has_key(app):
                docs[app].append((r[1], r[2]))
            else:
                docs[app] = [(r[1], r[2])]  # Ex: {'pres-rules': [('index.html', '4564fd9c9a2a2e3e796310b00c9908aa')]}
        return docs

    def get_documents_list(self, uri):
        return self.conn.runInteraction(self._get_documents_list, uri)


installSignalHandlers = True

def auth_db_connection(uri):
    conn = connectionForURI(uri)
    return conn

def storage_db_connection(uri):
    conn = connectionForURI(uri)
    def cb(res):
        if res[0:1][0:1] and res[0][0]:
            print '%s xcap documents in the database' % res[0][0]
        return res
    def eb(fail):
        fail.printTraceback()
        return fail
    # connect early, so database problem are detected early
    d = conn.runQuery('SELECT count(*) from %s' % Config.xcap_table)
    d.addCallback(cb)
    d.addErrback(eb)
    return conn

