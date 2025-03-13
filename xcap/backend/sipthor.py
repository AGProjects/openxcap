
import asyncio
import json
import re
import signal

from application import log
from application.configuration import ConfigSection, ConfigSetting
from application.configuration.datatypes import IPAddress
from application.notification import (IObserver, NotificationCenter,
                                      NotificationData)
from application.process import process
from application.python import Null
from application.python.types import Singleton
from application.system import host
from gnutls.interfaces.twisted import TLSContext, X509Credentials
from sipsimple.core import (SIPURI, Engine, FromHeader, Header, Publication,
                            RouteHeader)
from sqlmodel import select
from starlette.background import BackgroundTask, BackgroundTasks
from thor.entities import GenericThorEntity as ThorEntity
from thor.entities import ThorEntitiesRoleMap
from thor.eventservice import EventServiceClient, ThorEvent
from thor.link import ControlLink, Notification, Request
from twisted.internet import defer
from twisted.internet.defer import Deferred
from zope.interface import implementer

import xcap
from xcap.backend import BackendInterface, StatusResponse
from xcap.configuration import ServerConfig
from xcap.configuration.datatypes import DatabaseURI
from xcap.datatypes import XCAPRootURI
from xcap.db.manager import get_auth_db_session, get_db_session
from xcap.db.models import DataObject, SipAccount
from xcap.dbutil import make_random_etag
from xcap.errors import NotFound
from xcap.tls import Certificate, PrivateKey
from xcap.xcapdiff import Notifier


class ThorNodeConfig(ConfigSection):
    __cfgfile__ = "config.ini"
    __section__ = 'ThorNetwork'

    domain = "sipthor.net"
    multiply = 1000
    certificate = ConfigSetting(type=Certificate, value=None)
    private_key = ConfigSetting(type=PrivateKey, value=None)
    ca = ConfigSetting(type=Certificate, value=None)


class ServerConfig(ConfigSection):
    __cfgfile__ = "config.ini"  # Link to project documentation
    __section__ = 'Server'

    address = ConfigSetting(type=IPAddress, value='0.0.0.0')
    root = ConfigSetting(type=XCAPRootURI, value=None)
    tcp_port = 35060


class ThorEntityAddress(bytes):
    def __new__(cls, ip, control_port=None, version='unknown'):
        instance = super().__new__(cls, ip.encode('utf-8'))
        instance.ip = ip
        instance.version = version
        instance.control_port = control_port
        return instance


class GetSIPWatchers(Request):
    def __new__(cls, account):
        command = "get sip_watchers for %s" % account
        instance = Request.__new__(cls, command)
        return instance


class XCAPProvisioning(EventServiceClient, metaclass=Singleton):
    topics = ["Thor.Members"]

    def __init__(self):
        self.node = ThorEntity(host.default_ip if ServerConfig.address == '0.0.0.0' else ServerConfig.address, ['xcap_server'], control_port=25061, version=xcap.__version__)
        self.networks = {}
        self.presence_message = ThorEvent('Thor.Presence', self.node.id)
        self.shutdown_message = ThorEvent('Thor.Leave', self.node.id)
        credentials = X509Credentials(ThorNodeConfig.certificate, ThorNodeConfig.private_key, [ThorNodeConfig.ca])
        credentials.verify_peer = True
        tls_context = TLSContext(credentials)
        self.control = ControlLink(tls_context)
        EventServiceClient.__init__(self, ThorNodeConfig.domain, tls_context)
        process.signals.add_handler(signal.SIGHUP, self._handle_signal)
        process.signals.add_handler(signal.SIGINT, self._handle_signal)
        process.signals.add_handler(signal.SIGTERM, self._handle_signal)

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
            log.exception()
            node = None
        return node

    def notify(self, operation, entity_type, entity):
        node = self.lookup(entity)
        if node is not None:
            if node.control_port is None:
                log.error("Could not send notify because node %s has no control port" % node.ip)
                return
            self.control.send_request(Notification("notify %s %s %s" % (operation, entity_type, entity)), (node.ip, node.control_port))

    async def get_watchers(self, key):
        """
        Fetch watchers asynchronously.
        This method is called from asyncio code, so it will
        convert the Deferred returned by Twisted to a Future.
        """
        # Get the Deferred from the Twisted code
        deferred = self._get_watchers(key)

        # Wrap the Twisted Deferred into an asyncio Future and await it
        result = await self._deferred_to_future(deferred)

        return result

    async def _deferred_to_future(self, deferred):
        """
        Convert a Twisted Deferred into an asyncio Future.
        This allows us to await the Deferred in an async function.
        """
        # Wrap the Deferred into an asyncio Future
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        # Add a callback that will set the result on the asyncio Future when the Deferred is done
        deferred.addCallback(future.set_result)
        deferred.addErrback(future.set_exception)

        return await future

    def _get_watchers(self, key):
        node = self.lookup(key)
        if node is None:
            return defer.fail("no nodes found when searching for key %s" % str(key))
        if node.control_port is None:
            return defer.fail("could not send notify because node %s has no control port" % node.ip)
        request = GetSIPWatchers(key)
        request.deferred = Deferred()

        self.control.send_request(request, (node.ip, node.control_port))
        return request.deferred

    def handle_event(self, event):
        networks = self.networks
        role_map = ThorEntitiesRoleMap(event.message) ## mapping between role names and lists of nodes with that role
        thor_databases = role_map.get('thor_database', [])
        if thor_databases:
            # thor_databases.sort(lambda x, y: cmp(x.priority, y.priority) or cmp(x.ip, y.ip))
            thor_databases.sort(key=lambda x: (x.priority, x.ip))
            dburi = thor_databases[0].dburi
        else:
            dburi = None
        NotificationCenter().post_notification('db_uri', self, DatabaseURI(dburi))
        all_roles = list(role_map.keys()) + list(networks.keys())
        for role in all_roles:
            try:
                network = networks[role] ## avoid setdefault here because it always evaluates the 2nd argument
            except KeyError:
                from thor import network as thor_network
                if role in ["thor_manager", "thor_monitor", "provisioning_server", "media_relay", "thor_database"]:
                    continue
                else:
                    network = thor_network.new(ThorNodeConfig.multiply)
                networks[role] = network
            new_nodes = set([ThorEntityAddress(node.ip, getattr(node, 'control_port', None), getattr(node, 'version', 'unknown')) for node in role_map.get(role, [])])
            old_nodes = set(network.nodes)
            added_nodes = new_nodes - old_nodes
            removed_nodes = old_nodes - new_nodes
            if removed_nodes:
                for node in removed_nodes:
                    network.remove_node(node)
                    self.control.discard_link(node)
                plural = len(removed_nodes) != 1 and 's' or ''
                log.info("Removed %s node%s: %s" % (role, plural, ', '.join([node.decode() for node in removed_nodes])))
            if added_nodes:
                for node in added_nodes:
                    network.add_node(node)
                plural = len(added_nodes) != 1 and 's' or ''
                log.info("Added %s node%s: %s" % (role, plural, ', '.join([node.decode() for node in added_nodes])))
            # print('Thor %s nodes: %s' % (role, str(network.nodes)))


class NoDatabase(Exception):
    pass


class DatabaseConnection(object, metaclass=Singleton):
    async def put(self, uri, document, check_etag, new_etag):
        operation = lambda profile: self._put_operation(uri, document, check_etag, new_etag, profile)
        return await self.retrieve_profile(uri.user.username, uri.user.domain, operation, True)

    async def delete(self, uri, check_etag):
        operation = lambda profile: self._delete_operation(uri, check_etag, profile)
        return await self.retrieve_profile(uri.user.username, uri.user.domain, operation, True)

    async def delete_all(self, uri):
        operation = lambda profile: self._delete_all_operation(uri, profile)
        return await self.retrieve_profile(uri.user.username, uri.user.domain, operation, True)

    async def get(self, uri):
        operation = lambda profile: self._get_operation(uri, profile)
        return await self.retrieve_profile(uri.user.username, uri.user.domain, operation, False)
        return defer

    async def get_profile(self, username, domain):
        return await self.retrieve_profile(username, domain, lambda profile: profile, False)
        return defer

    async def get_documents_list(self, uri):
        operation = lambda profile: self._get_documents_list_operation(uri, profile)
        return await self.retrieve_profile(uri.user.username, uri.user.domain, operation, False)

    def _put_operation(self, uri, document, check_etag, new_etag, profile):
        xcap_docs = profile.setdefault("xcap", {})
        try:
            etag = xcap_docs[uri.application_id][uri.doc_selector.document_path][1]
        except KeyError:
            found = False
            etag = None
            check_etag(None, False)
        else:
            found = True
            check_etag(etag)
        xcap_app = xcap_docs.setdefault(uri.application_id, {})
        xcap_app[uri.doc_selector.document_path] = (document, new_etag)
        return found, etag, new_etag

    def _delete_operation(self, uri, check_etag, profile):
        xcap_docs = profile.setdefault("xcap", {})
        try:
            etag = xcap_docs[uri.application_id][uri.doc_selector.document_path][1]
        except KeyError:
            raise NotFound()
        check_etag(etag)
        del xcap_docs[uri.application_id][uri.doc_selector.document_path]
        return (etag)

    def _delete_all_operation(self, uri, profile):
        xcap_docs = profile.setdefault("xcap", {})
        xcap_docs.clear()
        return None

    def _get_operation(self, uri, profile):
        try:
            xcap_docs = profile["xcap"]
            doc, etag = xcap_docs[uri.application_id][uri.doc_selector.document_path]
        except KeyError:
            raise NotFound()
        return doc, etag

    def _get_documents_list_operation(self, uri, profile):
        try:
            xcap_docs = profile["xcap"]
        except KeyError:
            raise NotFound()
        return xcap_docs

    async def retrieve_profile(self, username, domain, operation, update):
        async with get_db_session() as db_session:
            query = await db_session.execute(select(SipAccount).where(
                SipAccount.username == username, SipAccount.domain == domain))
            db_result = query.first()
            if not db_result:
                raise NotFound()
            profile = db_result[0].profile
            result = operation(profile)
            if update:
                db_result[0].profile = profile
                await db_session.commit()
                await db_session.refresh(db_result[0])
            return result


class PasswordChecker(object):
    async def query_user(self, credentials):
        async with get_auth_db_session() as db_session:
            result = await db_session.execute(select(SipAccount).where(
                SipAccount.username == credentials.username, SipAccount.domain == credentials.realm))
            result = result.first()
            if result:
                return [DataObject(**result[0].profile)]
            return result


@implementer(IObserver)
class SIPNotifier(object, metaclass=Singleton):

    def __init__(self):
        self.provisioning = XCAPProvisioning()
        self.engine = Engine()
        self.engine.start(
            ip_address=None if ServerConfig.address == '0.0.0.0' else ServerConfig.address,
            user_agent="OpenXCAP %s" % xcap.__version__,
        )

    def send_publish(self, uri, body) -> None:
        uri = re.sub("^(sip:|sips:)", "", uri)
        destination_node = self.provisioning.lookup(uri)

        if destination_node is not None:
            # TODO: add configuration settings for SIP transport. -Saul
            publication = Publication(FromHeader(SIPURI(uri)),
                                      "xcap-diff",
                                      "application/xcap-diff+xml",
                                      duration=0,
                                      extra_headers=[Header('Thor-Scope', 'publish-xcap')])
            NotificationCenter().add_observer(self, sender=publication)
            route_header = RouteHeader(SIPURI(host=destination_node.decode(), port='5060', parameters=dict(transport='tcp')))
            publication.publish(body, route_header, timeout=5)

    def handle_notification(self, notification):
        handler = getattr(self, '_NH_%s' % notification.name, Null)
        handler(notification)

    def _NH_SIPPublicationDidSucceed(self, notification):
        log.info('PUBLISH xcap-diff sent to %s for %s' % (notification.data.route_header.uri, notification.sender.from_header.uri))

    def _NH_SIPPublicationDidEnd(self, notification):
        # log.info('PUBLISH for xcap-diff event ended for %s' % notification.sender.from_header.uri)
        NotificationCenter().remove_observer(self, sender=notification.sender)

    def _NH_SIPPublicationDidFail(self, notification):
        log.info('PUBLISH xcap-diff failed to %s for %s' % (notification.data.route_header.uri, notification.sender.from_header.uri))
        NotificationCenter().remove_observer(self, sender=notification.sender)


class Storage(BackendInterface):
    def __init__(self):
        self._database = DatabaseConnection()
        self._provisioning = XCAPProvisioning()
        self._sip_notifier = SIPNotifier()
        self._notifier = Notifier(ServerConfig.root, self._sip_notifier.send_publish)

    async def get_document(self, uri, check_etag):
        self._normalize_document_path(uri)
        result = await self._database.get(uri)
        return self._got_document(result, check_etag)
        result.addErrback(self._eb_not_found)
        return result

    def _got_document(self, xxx_todo_changeme, check_etag):
        (doc, etag) = xxx_todo_changeme
        check_etag(etag)
        return StatusResponse(200, etag, doc.encode('utf-8'))

    async def put_document(self, uri, document, check_etag):
        document = document.decode('utf-8')
        self._normalize_document_path(uri)
        etag = make_random_etag(uri)
        result = await self._database.put(uri, document, check_etag, etag)
        return self._cb_put(result, uri, "%s@%s" % (uri.user.username, uri.user.domain))
        return result

    def _cb_put(self, result, uri, thor_key):
        if result[0]:
            code = 200
        else:
            code = 201
        task = BackgroundTasks()
        task.add_task(BackgroundTask(self._provisioning.notify, "update", "sip_account", thor_key))
        task.add_task(BackgroundTask(self._notifier.on_change, uri, result[1], result[2]))
        return StatusResponse(code, result[2], background=task)

    async def delete_documents(self, uri):
        result = await self._database.delete_all(uri)
        return self._cb_delete_all(result, uri, "%s@%s" % (uri.user.username, uri.user.domain))

    def _cb_delete_all(self, result, uri, thor_key):
        task = BackgroundTasks()
        task.add_task(BackgroundTask(self._provisioning.notify, "update", "sip_account", thor_key))
        return StatusResponse(200, background=task)

    async def delete_document(self, uri, check_etag):
        self._normalize_document_path(uri)
        result = await self._database.delete(uri, check_etag)
        return self._cb_delete(result, uri, "%s@%s" % (uri.user.username, uri.user.domain))

    def _cb_delete(self, result, uri, thor_key):
        task = BackgroundTasks()
        task.add_task(BackgroundTask(self._provisioning.notify, "update", "sip_account", thor_key))
        task.add_task(BackgroundTask(self._notifier.on_change, uri, result[1], None))
        return StatusResponse(200, background=task)

    async def get_watchers(self, uri):
        thor_key = "%s@%s" % (uri.user.username, uri.user.domain)
        result = await self._provisioning.get_watchers(thor_key)
        return self._get_watchers_decode(result)

    def _get_watchers_decode(self, response):
        if response.code == 200:
            watchers = json.loads(response.data)
            for watcher in watchers:
                watcher["online"] = str(watcher["online"]).lower()
            return watchers
        else:
            print("error: %s" % response)

    async def get_documents_list(self, uri):
        result = await self._database.get_documents_list(uri)
        return self._got_documents_list(result)

    def _got_documents_list(self, xcap_docs):
        docs = {}
        if xcap_docs:
            for k, v in xcap_docs.items():
                for k2, v2 in v.items():
                    if k in docs:
                        docs[k].append((k2, v2[1]))
                    else:
                        docs[k] = [(k2, v2[1])]
        return docs


installSignalHandlers = False
