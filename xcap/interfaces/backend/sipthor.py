# Copyright (C) 2007 AG-Projects.
#
# This module is prorietary to AG-Projects. Use of this module by third
# parties is unsupported.

import signal

import cjson

from formencode import validators

from application import log
from application.python.util import Singleton
from application.system import default_host_ip
from application.process import process

from sqlobject import sqlhub, connectionForURI, SQLObject, AND
from sqlobject import StringCol, IntCol, DateTimeCol, SOBLOBCol, Col
from sqlobject import MultipleJoin, ForeignKey

from zope.interface import implements
from twisted.internet import reactor
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword, IUsernameHashedPassword
from twisted.cred.error import UnauthorizedLogin

from thor.control import ControlLink, Notification, Request
from thor.eventservice import EventServiceClient, ThorEvent
from thor.entities import ThorEntitiesRoleMap, GenericThorEntity as ThorEntity

from gnutls.interfaces.twisted import X509Credentials
from gnutls.constants import COMP_DEFLATE, COMP_LZO, COMP_NULL

from xcap.config import ConfigFile, ConfigSection
from xcap.tls import Certificate, PrivateKey
from xcap.interfaces.backend import StatusResponse
from xcap.dbutil import generate_etag

class ThorNodeConfig(ConfigSection):
    _datatypes = {'certificate': Certificate, 'private_key': PrivateKey, 'ca': Certificate}
    certificate = None
    private_key = None
    ca = None

class ThorNetworkConfig(ConfigSection):
    domain = "sipthor.net"
    multiply = 1000


class JSONValidator(validators.Validator):

    def to_python(self, value, state):
        if value is None:
            return None
        try:
            return cjson.decode(value)
        except Exception:
            raise validators.Invalid("expected a decodable JSON object in the JSONCol '%s', got %s %r instead" % (self.name, type(value), value), value, state)

    def from_python(self, value, state):
        if value is None:
            return None
        try:
            return cjson.encode(value)
        except Exception:
            raise validators.Invalid("expected an encodable JSON object in the JSONCol '%s', got %s %r instead" % (self.name, type(value), value), value, state)


class SOJSONCol(SOBLOBCol):

    def createValidators(self):
        return [JSONValidator()] + super(SOJSONCol, self).createValidators()


class JSONCol(Col):
    baseClass = SOJSONCol


class SipAccount(SQLObject):
    class sqlmeta:
        table = 'sip_accounts_meta'
    username   = StringCol(length=64)
    domain     = StringCol(length=64)
    firstName  = StringCol(length=64)
    lastName   = StringCol(length=64)
    email      = StringCol(length=64)
    customerId = IntCol(default=0)
    resellerId = IntCol(default=0)
    ownerId    = IntCol(default=0)
    changeDate = DateTimeCol(default=DateTimeCol.now)
    ## joins
    data       = MultipleJoin('SipAccountData', joinColumn='account_id')

    def _set_profile(self, value):
        data = list(self.data)
        if not data:
            SipAccountData(account=self, profile=value)
        else:
            data[0].profile = value

    def _get_profile(self):
        return self.data[0].profile

    def set(self, **kwargs):
        kwargs = kwargs.copy()
        profile = kwargs.pop('profile', None)
        SQLObject.set(self, **kwargs)
        if profile is not None:
            self._set_profile(profile)


class SipAccountData(SQLObject):
    class sqlmeta:
        table = 'sip_accounts_data'
    account  = ForeignKey('SipAccount', cascade=True)
    profile  = JSONCol()


configuration = ConfigFile()
configuration.read_settings('ThorNode', ThorNodeConfig)
configuration.read_settings('ThorNetwork', ThorNetworkConfig)

def sanitize_application_id(application_id):
    if application_id == "org.openmobilealliance.pres-rules":
        return "pres-rules"
    else:
        return application_id

class GetOnlineDevices(Request):
    def __new__(cls, account):
        command = "get_watchers for %s" % account
        instance = Request.__new__(cls, command)
        return instance


class XCAPProvisioning(EventServiceClient):
    __metaclass__ = Singleton
    topics = ["Thor.Members"]

    def __init__(self):
        self._database = DatabaseConnection()
        self.node = ThorEntity(default_host_ip, ['xcap_server'])
        self.networks = {}
        self.presence_message = ThorEvent('Thor.Presence', self.node.id)
        self.shutdown_message = ThorEvent('Thor.Leave', self.node.id)
        credentials = X509Credentials(ThorNodeConfig.certificate, ThorNodeConfig.private_key, [ThorNodeConfig.ca])
        credentials.verify_peer = True
        credentials.session_params.compressions = (COMP_LZO, COMP_DEFLATE, COMP_NULL)
        self.control = ControlLink(credentials)
        EventServiceClient.__init__(self, ThorNetworkConfig.domain, credentials)
        process.signals.add_handler(signal.SIGHUP, self._handle_SIGHUP)
        process.signals.add_handler(signal.SIGINT, self._handle_SIGINT)
        process.signals.add_handler(signal.SIGTERM, self._handle_SIGTERM)

    def _disconnect_all(self, result):
        self.control.disconnect_all()
        EventServiceClient._disconnect_all(self, result)

    def lookup(self, key):
        network = self.networks.get("sip_proxy", None)
        if network is None:
            return None
        try:
            node = network.lookup_node(key)
        except LookupError:
            node = None
        except Exception:
            log.err()
            node = None
        return node

    def notify(self, operation, entity_type, entity):
        node = self.lookup(entity)
        if node is not None:
            self.control.send_request(Notification("notify %s %s %s" % (operation, entity_type, entity)), node)

    def get_watchers(self, key):
        node = self.lookup(key)
        request = GetOnlineDevices(key)
        request.deferred = Deferred()
        self.control.send_request(request, node)
        return request.deferred

    def handle_event(self, event):
        # print "Received event: %s" % event
        networks = self.networks
        role_map = ThorEntitiesRoleMap(event.message) ## mapping between role names and lists of nodes with that role
        thor_databases = role_map.get('thor_database', [])
        if thor_databases:
            thor_databases.sort(lambda x, y: cmp(x.priority, y.priority) or cmp(x.ip, y.ip))
            dburi = thor_databases[0].dburi
        else:
            dburi = None
        self._database.update_dburi(dburi)
        all_roles = role_map.keys() + networks.keys()
        for role in all_roles:
            try:
                network = networks[role] ## avoid setdefault here because it always evaluates the 2nd argument
            except KeyError:
                from thor import network as thor_network
                if role in ["thor_manager", "thor_monitor", "provisioning_server", "media_relay"]:
                    continue
                else:
                    network = thor_network.new(ThorNetworkConfig.multiply)
                networks[role] = network
            new_nodes = set([node.ip for node in role_map.get(role, [])])
            old_nodes = set(network.nodes)
            ## compute set differences
            added_nodes = new_nodes - old_nodes
            removed_nodes = old_nodes - new_nodes
            if removed_nodes:
                for node in removed_nodes:
                    network.remove_node(node)
                    self.control.discard_node(node)
                plural = len(removed_nodes) != 1 and 's' or ''
                log.msg("removed %s node%s: %s" % (role, plural, ', '.join(removed_nodes)))
            if added_nodes:
                for node in added_nodes:
                    network.add_node(node)
                plural = len(added_nodes) != 1 and 's' or ''
                log.msg("added %s node%s: %s" % (role, plural, ', '.join(added_nodes)))
            #print "Thor %s nodes: %s" % (role, str(network.nodes))


class NotFound(Exception):
    pass


class NoDatabase(Exception):
    pass


class DatabaseConnection(object):
    __metaclass__ = Singleton

    def __init__(self):
        self.dburi = None

    # Methods to be called from the Twisted thread:
    def put(self, uri, document, check_etag, new_etag):
        defer = Deferred()
        operation = lambda profile: self._put_operation(uri, document, check_etag, new_etag, profile)
        reactor.callInThread(self.retrieve_profile, uri.user.username, uri.user.domain, operation, True, defer)
        return defer

    def delete(self, uri, check_etag):
        defer = Deferred()
        operation = lambda profile: self._delete_operation(uri, check_etag, profile)
        reactor.callInThread(self.retrieve_profile, uri.user.username, uri.user.domain, operation, True, defer)
        return defer

    def get(self, uri):
        defer = Deferred()
        operation = lambda profile: self._get_operation(uri, profile)
        reactor.callInThread(self.retrieve_profile, uri.user.username, uri.user.domain, operation, False, defer)
        return defer

    def get_profile(self, username, domain):
        defer = Deferred()
        reactor.callInThread(self.retrieve_profile, username, domain, lambda profile: profile, False, defer)
        return defer

    # Methods to be called in a separate thread:
    def _put_operation(self, uri, document, check_etag, new_etag, profile):
        application_id = sanitize_application_id(uri.application_id)
        xcap_docs = profile.setdefault("xcap", {})
        try:
            etag = xcap_docs[application_id][uri.doc_selector.document_path][1]
        except KeyError:
            found = False
        else:
            found = True
            check_etag(etag)
        xcap_app = xcap_docs.setdefault(application_id, {})
        xcap_app[uri.doc_selector.document_path] = (document, new_etag)
        return found

    def _delete_operation(self, uri, check_etag, profile):
        application_id = sanitize_application_id(uri.application_id)
        xcap_docs = profile.setdefault("xcap", {})
        try:
            etag = xcap_docs[application_id][uri.doc_selector.document_path][1]
        except KeyError:
            raise NotFound()
        check_etag(etag)
        del(xcap_docs[application_id][uri.doc_selector.document_path])
        return None

    def _get_operation(self, uri, profile):
        try:
            xcap_docs = profile["xcap"]
            doc, etag = xcap_docs[sanitize_application_id(uri.application_id)][uri.doc_selector.document_path]
        except KeyError:
            raise NotFound()
        return doc, etag

    def retrieve_profile(self, username, domain, operation, update, defer):
        transaction = None
        try:
            if self.dburi is None:
                raise NoDatabase()
            transaction = sqlhub.processConnection.transaction()
            try:
                db_account = SipAccount.select(AND(SipAccount.q.username == username, SipAccount.q.domain == domain), connection = transaction, forUpdate = update)[0]
            except IndexError:
                raise NotFound()
            profile = db_account.profile
            result = operation(profile) # NB: may modify profile!
            if update:
                db_account.profile = profile
            transaction.commit(close=True)
        except Exception, e:
            if transaction:
                transaction.rollback()
            reactor.callFromThread(defer.errback, e)
        else:
            reactor.callFromThread(defer.callback, result)

    def update_dburi(self, dburi):
        if self.dburi != dburi:
            if self.dburi is not None:
                sqlhub.processConnection.close()
            if dburi is None:
                sqlhub.processConnection
            else:
                sqlhub.processConnection = connectionForURI(dburi)
            self.dburi = dburi


class SipthorPasswordChecker(object):
    implements(ICredentialsChecker)
    credentialInterfaces = (IUsernamePassword, IUsernameHashedPassword)

    def __init__(self):
        self._database = DatabaseConnection()

    def _query_credentials(self, credentials):
        username, domain = credentials.username.split('@', 1)[0], credentials.realm
        result = self._database.get_profile(username, domain)
        result.addCallback(self._got_query_results, credentials)
        result.addErrback(self._got_unsuccessfull)
        return result

    def _got_unsuccessfull(self, failure):
        failure.trap(NotFound)
        raise UnauthorizedLogin("Unauthorized login")

    def _got_query_results(self, profile, credentials):
        return self._authenticate_credentials(profile, credentials)

    def _authenticate_credentials(self, profile, credentials):
        raise NotImplementedError

    def _checkedPassword(self, matched, username, realm):
        if matched:
            username = username.split('@', 1)[0]
            ## this is the avatar ID
            return "%s@%s" % (username, realm)
        else:
            raise UnauthorizedLogin("Unauthorized login")

    def requestAvatarId(self, credentials):
        """Return the avatar ID for the credentials which must have the username
           and realm attributes, or an UnauthorizedLogin in case of a failure."""
        d = self._query_credentials(credentials)
        return d


class PlainPasswordChecker(SipthorPasswordChecker):
    """A credentials checker against a database subscriber table, where the passwords
       are stored in plain text."""

    implements(ICredentialsChecker)

    def _authenticate_credentials(self, profile, credentials):
        return maybeDeferred(
                credentials.checkPassword, profile["password"]).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)


class HashPasswordChecker(SipthorPasswordChecker):
    """A credentials checker against a database subscriber table, where the passwords
       are stored as MD5 hashes."""

    implements(ICredentialsChecker)

    def _authenticate_credentials(self, profile, credentials):
        return maybeDeferred(
                credentials.checkHash, profile["ha1"]).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)

class Storage(object):
    __metaclass__ = Singleton

    def __init__(self):
        self._database = DatabaseConnection()
        self._provisioning = XCAPProvisioning()

    def _normalize_document_path(self, uri):
        ## some clients e.g. counterpath's eyebeam save presence rules under
        ## different filenames between versions and they expect to find the same
        ## information, thus we are forcing all presence rules documents to be
        ## saved under "index.xml" default filename
        if uri.application_id in ("org.openmobilealliance.pres-rules", "pres-rules"):
            uri.doc_selector.document_path = "index.xml"

    def get_document(self, uri, check_etag):
        self._normalize_document_path(uri)
        result = self._database.get(uri)
        result.addCallback(self._got_document, check_etag)
        result.addErrback(self._eb_not_found)
        return result

    def _eb_not_found(self, failure):
        failure.trap(NotFound)
        return StatusResponse(404)

    def _got_document(self, (doc, etag), check_etag):
        check_etag(etag)
        return StatusResponse(200, etag, doc)

    def put_document(self, uri, document, check_etag):
        self._normalize_document_path(uri)
        etag = generate_etag(uri, document)
        result = self._database.put(uri, document, check_etag, etag)
        result.addCallback(self._cb_put, etag, "%s@%s" % (uri.user.username, uri.user.domain))
        result.addErrback(self._eb_not_found)
        return result

    def _cb_put(self, found, etag, thor_key):
        if found:
            code = 200
        else:
            code = 201
        self._provisioning.notify("update", "sip_account", thor_key)
        return StatusResponse(code, etag)

    def delete_document(self, uri, check_etag):
        self._normalize_document_path(uri)
        result = self._database.delete(uri, check_etag)
        result.addCallback(self._cb_delete, "%s@%s" % (uri.user.username, uri.user.domain))
        result.addErrback(self._eb_not_found)
        return result

    def _cb_delete(self, nothing, thor_key):
        self._provisioning.notify("update", "sip_account", thor_key)
        return StatusResponse(200)

    def get_watchers(self, uri):
        thor_key = "%s@%s" % (uri.user.username, uri.user.domain)
        result = self._provisioning.get_watchers(thor_key)
        result.addCallback(self._get_watchers_decode)
        return result

    def _get_watchers_decode(self, response):
        if response.code == 200:
            watchers = cjson.decode(response.data)
            for watcher in watchers:
                watcher["online"] = str(watcher["online"]).lower()
            return watchers
        else:
            print "error: %s" % response

installSignalHandlers = False
