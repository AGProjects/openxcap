# Copyright (C) 2007 AG-Projects.
#
# This module is prorietary to AG-Projects. Use of this module by third
# parties is unsupported.

import md5
from time import time
from Queue import Queue

import cjson

from application import log
from application.configuration import *
from application.python.util import Singleton
from application.system import default_host_ip

from sqlobject import sqlhub, connectionForURI, SQLObject, AND
from sqlobject import StringCol, IntCol, BLOBCol, DateTimeCol

from zope.interface import implements
from twisted.internet import reactor
from twisted.python.failure import Failure
from twisted.internet.defer import Deferred, maybeDeferred
from twisted.internet.protocol import ClientFactory
from twisted.names.srvconnect import SRVConnector
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword, IUsernameHashedPassword
from twisted.cred.error import UnauthorizedLogin

from thor.control import ControlLink, Notification, Request
from thor.eventservice import EventServiceClient, ThorEvent
from thor.entities import ThorEntitiesRoleMap, GenericThorEntity as ThorEntity

from gnutls.interfaces.twisted import X509Credentials
from gnutls.constants import *

from xcap.tls import Certificate, PrivateKey
from xcap.interfaces.backend import IStorage, StatusResponse
from xcap.interfaces.backend.memcache import MemcacheProtocol, DisconnectedError, CommandUnsuccessful

class Config(ConfigSection):
    _datatypes = {'certificate': Certificate, 'private_key': PrivateKey, 'ca': Certificate,
                  'memcache_certificate': Certificate, 'memcache_private_key': PrivateKey,
                  'memcache_host': str, 'memcache_port': int}
    certificate = None
    private_key = None
    ca = None
    memcache_host = None
    memcache_port = None
    memcache_certificate = None
    memcache_private_key = None
    dburi = "mysql://user:pass@db/sipthor"
    nodeIP = default_host_ip

class ThorNetworkConfig(ConfigSection):
    domain = "sipthor.net"
    multiply = 1000

class SIPAccount(SQLObject):
    class sqlmeta:
        table = 'sip_accounts'
        cacheValues = False
    username     = StringCol(length = 64, notNone = True)
    domain       = StringCol(length = 128, notNone = True)
    password     = StringCol(length = 25, notNone = True)
    customerId   = IntCol(length = 20, default = 0, notNone = True)
    resellerId   = IntCol(length = 20, default = 0, notNone = True)
    ownerId      = IntCol(length = 20, default = 0, notNone = True)
    profile      = BLOBCol()


configuration = ConfigFile('config.ini')
configuration.read_settings('SIPThor', Config)
configuration.read_settings('ThorNetwork', ThorNetworkConfig)

sqlhub.processConnection = connectionForURI(Config.dburi)

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
        self.node = ThorEntity(Config.nodeIP, ['xcap_server'])
        self.networks = {}
        self.presence_message = ThorEvent('Thor.Presence', self.node.id)
        self.shutdown_message = ThorEvent('Thor.Leave', self.node.id)
        credentials = X509Credentials(Config.certificate, Config.private_key, [Config.ca])
        credentials.verify_peer = True
        credentials.session_params.compressions = (COMP_LZO, COMP_DEFLATE, COMP_NULL)
        self.control = ControlLink(credentials)
        EventServiceClient.__init__(self, ThorNetworkConfig.domain, credentials)

    def _disconnect_all(self, result):
        self.control.disconnect_all()
        EventServiceClient._disconnect_all(self, result)

    def lookup(self, key):
        prefix, id = key.split(':', 1)
        network = self.networks.get("sip_proxy", None)
        if network is None:
            return None
        try:
            node = network.lookup_node(id)
        except LookupError:
            node = None
        except:
            log.msg("Error doing Thor ID lookup")
            log.err()
            node = None
        return node

    def notify(self, action, key):
        node = self.lookup(key)
        if node is not None:
            self.control.send_request(Notification("notify %s %s" % (action, key)), node)

    def get_watchers(self, key):
        node = self.lookup(key)
        prefix, account = key.split(':', 1)
        request = GetOnlineDevices(account)
        request.deferred = Deferred()
        self.control.send_request(request, node)
        return request.deferred

    def handle_event(self, event):
        # print "Received event: %s" % event
        networks = self.networks
        role_map = ThorEntitiesRoleMap(event.message) ## mapping between role names and lists of nodes with that role
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


class DeleteNotFound(Exception):
    pass


class DatabaseConnection(object):
    __metaclass__ = Singleton

    # Methods to be called from the Twisted thread:
    def __init__(self):
        self._memcache = MemcacheConnection()

    def put(self, uri, document, check_etag, new_etag):
        defer = Deferred()
        operation = lambda profile: self._put_operation(uri, document, check_etag, new_etag, profile)
        reactor.callInThread(self.modify_profile, uri.user.username, uri.user.domain, operation, defer)
        return defer

    def delete(self, uri, check_etag):
        defer = Deferred()
        operation = lambda profile: self._delete_operation(uri, check_etag, profile)
        reactor.callInThread(self.modify_profile, uri.user.username, uri.user.domain, operation, defer)
        return defer

    def _memcache_from_thread(self, return_queue, cmd, *args, **kwargs):
        result = self._memcache.try_cmd(cmd, *args, **kwargs)
        result.addBoth(self._cb_memcache_from_thread, return_queue)

    def _cb_memcache_from_thread(self, result, return_queue):
        return_queue.put(result)

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
            raise DeleteNotFound()
        check_etag(etag)
        del(xcap_docs[application_id][uri.doc_selector.document_path])
        return None

    def _do_memcache_cmd(self, cmd, *args, **kwargs):
        queue = Queue(1)
        reactor.callFromThread(self._memcache_from_thread, queue, cmd, *args, **kwargs)
        result = queue.get(True, 10)
        if isinstance(result, Failure):
            raise result.value
        else:
            return result

    def modify_profile(self, username, domain, operation, defer):
        transaction = None
        try:
            transaction = sqlhub.processConnection.transaction()
            db_account = SIPAccount.select(AND(SIPAccount.q.username == username, SIPAccount.q.domain == domain), forUpdate = True)[0]
            profile = cjson.decode(db_account.profile)
            result = operation(profile) # NB: modifies profile!
            data = cjson.encode(profile)
            self._do_memcache_cmd("set", "sip:%s@%s" % (username, domain), data)
            db_account.profile = data
        except Exception, e:
            transaction.rollback()
            reactor.callFromThread(defer.errback, e)
        else:
            transaction.commit()
            reactor.callFromThread(defer.callback, result)


class MemcacheConnection(ClientFactory, object):
    __metaclass__ = Singleton
    commands = ["get", "set"]

    def __init__(self):
        self.protocol = None
        self.queue = []
        if Config.memcache_certificate is None or Config.memcache_private_key is None or Config.ca is None:
            use_tls = False
        else:
            use_tls = True
            credentials = X509Credentials(Config.memcache_certificate, Config.memcache_private_key, [Config.ca])
            credentials.verify_peer = True
        if Config.memcache_host is None or Config.memcache_port is None:
            if use_tls:
                connector = SRVConnector(reactor, "memcache", ThorNetworkConfig.domain, self,
                                         connectFuncName = "connectTLS", connectFuncArgs = [credentials])
            else:
                connector = SRVConnector(reactor, "memcache", ThorNetworkConfig.domain, self,
                                         connectFuncName = "connectTCP")
            connector.connect()
        else:
            if use_tls:
                reactor.connectTLS(Config.memcache_host, Config.memcache_port, self, credentials)
            else:
                reactor.connectTCP(Config.memcache_host, Config.memcache_port, self)

    def __getattr__(self, name):
        if name in self.commands:
            return lambda *args, **kwargs: self.try_cmd(name, *args, **kwargs)
        else:
            raise AttributeError

    def try_cmd(self, cmd, *args, **kwargs):
        if self.protocol is not None:
            return self._do_cmd(cmd, *args, **kwargs)
        else:
            defer = Deferred()
            self.queue.append((defer, cmd, args, kwargs))
            return defer

    def _do_cmd(self, cmd, *args, **kwargs):
        return self.protocol.do_command(cmd, *args, **kwargs)

    def _send_backlog(self):
        for defer, cmd, args, kwargs in self.queue:
            result = self._do_cmd(cmd, *args, **kwargs)
            result.chainDeferred(defer)
        self.queue = []

    def buildProtocol(self, addr):
        self.protocol = MemcacheProtocol()
        reactor.callLater(0, self._send_backlog) # We cannot do this directly as the protocol does not have a transport yet
        return self.protocol

    def clientConnectionLost(self, connector, reason):
        log.warn("Connection to memcached server lost, reconnecting: %s" % reason.value)
        reactor.callLater(1, connector.connect)

    def clientConnectionFailed(self, connector, reason):
        log.error("Connection to memcached server failed, retrying in 60 seconds: %s" % reason.value)
        for defer, cmd, args, kwargs in self.queue:
            defer.errback()
        self.queue = []
        reactor.callLater(60, connector.connect)

class MemcachePasswordChecker(object):
    """A credentials checker against memcached contents."""

    implements(ICredentialsChecker)

    credentialInterfaces = (IUsernamePassword, IUsernameHashedPassword)

    def __init__(self):
        self._memcache = MemcacheConnection()

    def _query_credentials(self, credentials):
        username, domain = credentials.username.split('@', 1)[0], credentials.realm
        result = self._memcache.get("sip:%s@%s" % (username, domain))
        result.addCallback(self._got_query_results, credentials)
        result.addErrback(self._got_unsuccessfull)
        return result

    def _got_unsuccessfull(self, failure):
        failure.trap(CommandUnsuccessful)
        raise UnauthorizedLogin("Unauthorized login")

    def _got_query_results(self, (blob, flags), credentials):
        profile = cjson.decode(blob)
        return self._authenticate_credentials(profile, credentials)

    def _authenticate_credentials(self, password, credentials):
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


class PlainPasswordChecker(MemcachePasswordChecker):
    """A credentials checker against a database subscriber table, where the passwords
       are stored in plain text."""

    implements(ICredentialsChecker)

    def _authenticate_credentials(self, profile, credentials):
        return maybeDeferred(
                credentials.checkPassword, profile["password"]).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)


class HashPasswordChecker(MemcachePasswordChecker):
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
        self._memcache = MemcacheConnection()
        self._database = DatabaseConnection()
        self._provisioning = XCAPProvisioning()

    def get_document(self, uri, check_etag):
        memkey = "sip:%s@%s" % (uri.user.username, uri.user.domain)
        result = self._memcache.get(memkey)
        result.addCallback(self._get_got_blob, uri, check_etag)
        return result

    def _get_got_blob(self, (blob, flags), uri, check_etag):
        profile = cjson.decode(blob)
        try:
            xcap_docs = profile["xcap"]
            doc, etag = xcap_docs[sanitize_application_id(uri.application_id)][uri.doc_selector.document_path]
        except KeyError:
            return StatusResponse(404)
        check_etag(etag)
        return StatusResponse(200, etag, doc)

    def put_document(self, uri, document, check_etag):
        etag = self.generate_etag(uri, document)
        result = self._database.put(uri, document, check_etag, etag)
        result.addCallback(self._cb_put, etag, "sip:%s@%s" % (uri.user.username, uri.user.domain))
        return result

    def _cb_put(self, found, etag, thor_key):
        if found:
            code = 200
        else:
            code = 201
        self._provisioning.notify("update", thor_key)
        return StatusResponse(code, etag)

    def delete_document(self, uri, check_etag):
        result = self._database.delete(uri, check_etag)
        result.addCallback(self._cb_delete, "sip:%s@%s" % (uri.user.username, uri.user.domain))
        result.addErrback(self._eb_delete)
        return result

    def _cb_delete(self, nothing, thor_key):
        self._provisioning.notify("update", thor_key)
        return StatusResponse(200)

    def _eb_delete(self, failure):
        failure.trap(DeleteNotFound)
        return StatusResponse(404)

    def generate_etag(self, uri, document):
        return md5.new(uri.xcap_root + str(uri.doc_selector) + str(time())).hexdigest()

    def get_watchers(self, uri):
        thor_key = "sip:%s@%s" % (uri.user.username, uri.user.domain)
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
