
import asyncio
import json
import re
import signal

from application import log
from application.configuration import ConfigSection, ConfigSetting
from application.configuration.datatypes import IPAddress
from application.notification import IObserver, NotificationCenter
from application.process import process
from application.python import Null
from application.python.types import Singleton
from application.system import host
from formencode import validators
from gnutls.interfaces.twisted import TLSContext, X509Credentials
from sipsimple.configuration.datatypes import Port
from sipsimple.core import (SIPURI, Engine, FromHeader, Header, Publication,
                            RouteHeader)
from sipsimple.threading import run_in_twisted_thread
from sqlmodel import Session, select
from sqlobject import (AND, Col, DateTimeCol, ForeignKey, IntCol, MultipleJoin,
                       SOBLOBCol, SQLObject, StringCol, connectionForURI,
                       sqlhub)
from starlette.background import BackgroundTask, BackgroundTasks
from thor.entities import GenericThorEntity as ThorEntity
from thor.entities import ThorEntitiesRoleMap
from thor.eventservice import EventServiceClient, ThorEvent
from thor.link import ControlLink, Notification, Request
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernameHashedPassword, IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.internet import asyncioreactor as reactor
from twisted.internet import defer
from twisted.internet.defer import Deferred, inlineCallbacks, maybeDeferred
from zope.interface import implementer

import xcap
from xcap.backend import BackendInterface, StatusResponse
from xcap.configuration import ServerConfig
from xcap.configuration.datatypes import DatabaseURI
from xcap.datatypes import XCAPRootURI
from xcap.db.manager import get_auth_db_session, get_db_session
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


class JSONValidator(validators.Validator):

    def to_python(self, value, state):
        if value is None:
            return None
        try:
            return json.loads(value)
        except Exception:
            raise validators.Invalid("expected a decodable JSON object in the JSONCol '%s', got %s %r instead" % (self.name, type(value), value), value, state)

    def from_python(self, value, state):
        if value is None:
            return None
        try:
            return json.dumps(value)
        except Exception:
            raise validators.Invalid("expected an encodable JSON object in the JSONCol '%s', got %s %r instead" % (self.name, type(value), value), value, state)


class SOJSONCol(SOBLOBCol):

    def createValidators(self):
        return [JSONValidator()] + super(SOJSONCol, self).createValidators()


class JSONCol(Col):
    baseClass = SOJSONCol

import asyncio
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column
# from typing import Optional, Any
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import Field, Relationship, SQLModel


class DataObject(BaseModel):
    class Config:
        # Allow extra fields in the data object and treat them as attributes
        extra = "allow"


class SipAccountData(SQLModel, table=True):
    __tablename__ = 'sip_accounts_data'
    id: int = Field(default=None, primary_key=True)
    account_id: int = Field(default=None, foreign_key="sip_accounts_meta.id")
    profile: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    account: "SipAccount" = Relationship(back_populates="data",
                                         sa_relationship_kwargs={"lazy": "joined"},
                                         )

class SipAccount(SQLModel, table=True):
    __tablename__ = 'sip_accounts_meta'
    id: int = Field(default=None, primary_key=True)
    username: str = Field(max_length=64)
    domain: str = Field(max_length=64)
    first_name: Optional[str] = Field(default=None, max_length=64)
    last_name: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=64)
    customer_id: int = Field(default=0)
    reseller_id: int = Field(default=0)
    owner_id: int = Field(default=0)
    change_date: Optional[str] = Field(default=None)

    # Relationships
    data: List[SipAccountData] = Relationship(back_populates="account",
                                              sa_relationship_kwargs={"lazy": "joined"},
                                              # cascade='all, delete-orphan'
                                              )

    def set_profile(self, value: dict):
        # this replaces the method to set the profile
#        data = list(self.data)
        if not self.data:
            SipAccountData(account=self, profile=value)
        else:
            flag_modified(self.data[0], "profile")
            self.data[0].profile = value

    @property
    def profile(self) -> Optional[dict]:
        return self.data[0].profile if self.data else None

    # def __setattr__(self, name, value):
    #     """
    #     Override __setattr__ to automatically handle updates to attributes.
    #     This is where we can implement custom logic for specific fields, such as profile.
    #     """
    #     # Handle special case for `profile`
    #     if name == "profile":
    #         print("name is profile")
    #         if self.data:
    #             # If data exists, set profile on the first related record
    #             print(f"set data \n{self.data[0].profile}\n to \n{value}\n")
    #             self.data[0].profile = value
    #         else:
    #             # Otherwise, create a new SipAccountData record with the profile
    #             new_data = SipAccountData(account_id=self.id, profile=value)
    #             self.data.append(new_data)
    #     else:
    #         # For other fields, just use the default behavior
    #         super().__setattr__(name, value)


    @profile.setter
    def profile(self, value: Optional[str]):
        self.set_profile(value)
    #     """Setter for the profile to the first SipAccountData."""
    #     print(f"setter name is profile {self.data}")
    #     if self.data:
    #         self.data[0].profile = value
    #     else:
    #         # If no related SipAccountData exists, create one
    #         new_data = SipAccountData(account_id=self.id, profile=value)
    #         self.data.append(new_data)
    #     # Track the modification of the SipAccountData object
    #     if self.data:
    #         # Add the first SipAccountData instance to the session, if modified
    #         db_session.add(self.data[0])  # Explicitly add to session
# class SipAccountData(SQLObject):
#     class sqlmeta:
#         table = 'sip_accounts_data'
#     account  = ForeignKey('SipAccount', cascade=True)
#     profile  = JSONCol()

from application.notification import (IObserver, NotificationCenter,
                                      NotificationData)

# class ThorEntityAddress(str):
#     def __new__(cls, ip, control_port=None, version='unknown'):
#         instance = super().__new__(cls, ip)
#         instance.ip = ip
#         instance.version = version
#         instance.control_port = control_port
#         return instance

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
        self.node = ThorEntity(host.default_ip if ServerConfig.address == '0.0.0.0' else ServerConfig.address, ['xcap_server'], control_port=25061 ,version=xcap.__version__)
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
#        print("Received event: %s" % event)
        networks = self.networks
        role_map = ThorEntitiesRoleMap(event.message) ## mapping between role names and lists of nodes with that role
        thor_databases = role_map.get('thor_database', [])
        if thor_databases:
            # thor_databases.sort(lambda x, y: cmp(x.priority, y.priority) or cmp(x.ip, y.ip))
            thor_databases.sort(key=lambda x: (x.priority, x.ip))
            dburi = thor_databases[0].dburi
        else:
            dburi = None
        # print(f"set updated {dburi}")
#        configure_db_connection(dburi)
        NotificationCenter().post_notification('db_uri', self, DatabaseURI(dburi))
        #loop = asyncio.get_event_loop()
        #loop.call_soon_threadsafe(configure_db_connection, uri)
        # self._database.update_dburi(dburi)
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
            # for item in new_nodes:
            #     print(item.control_port)
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
                    # print(type(network))
                    # print(type(node))
                    # print(node.control_port)
                    network.add_node(node)
                    # new = network.lookup_node(node)
                    # print(f'{new} - {new.control_port}')
                plural = len(added_nodes) != 1 and 's' or ''
                log.info("Added %s node%s: %s" % (role, plural, ', '.join([node.decode() for node in added_nodes])))
        # print(networks.nodes)
            # print('Thor %s nodes: %s' % (role, str(network.nodes)))


# class NotFound(HTTPError):
#     pass
#

class NoDatabase(Exception):
    pass


class DatabaseConnection(object, metaclass=Singleton):
    # def __init__(self):
    #     self.dburi = None

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
        del(xcap_docs[uri.application_id][uri.doc_selector.document_path])
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


@implementer(ICredentialsChecker)
class SipthorPasswordChecker(object):
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


@implementer(ICredentialsChecker)
class PlainPasswordChecker(SipthorPasswordChecker):
    """A credentials checker against a database subscriber table, where the passwords
       are stored in plain text."""


    def _authenticate_credentials(self, profile, credentials):
        return maybeDeferred(
                credentials.checkPassword, profile["password"]).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)


@implementer(ICredentialsChecker)
class HashPasswordChecker(SipthorPasswordChecker):
    """A credentials checker against a database subscriber table, where the passwords
       are stored as MD5 hashes."""


    def _authenticate_credentials(self, profile, credentials):
        return maybeDeferred(
                credentials.checkHash, profile["ha1"]).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)

@implementer(IObserver)
class SIPNotifier(object, metaclass=Singleton):

    def __init__(self):
        self.provisioning = XCAPProvisioning()
        self.engine = Engine()
        self.engine.start(
            ip_address=None if ServerConfig.address == '0.0.0.0' else ServerConfig.address,
            #tcp_port=ServerConfig.tcp_port,
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
        #log.info('PUBLISH for xcap-diff event ended for %s' % notification.sender.from_header.uri)
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
        # print(result)
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
