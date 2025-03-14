import re
from typing import Callable, Optional, Union

from application import log
from application.configuration import ConfigSetting
from application.notification import (IObserver, Notification,
                                      NotificationCenter)
from application.python import Null
from application.python.types import Singleton
from sipsimple.configuration.datatypes import SIPProxyAddress
from sipsimple.core import (SIPURI, Engine, FromHeader, Header, Publication,
                            RouteHeader)
from sipsimple.lookup import DNSLookup
from sipsimple.threading.green import run_in_green_thread
from starlette.background import BackgroundTask
from zope.interface import implementer

from xcap import __version__
from xcap.backend import StatusResponse
from xcap.backend.database import DatabaseStorage, PasswordChecker
from xcap.configuration import OpensipsConfig as XCAPOpensipsConfig
from xcap.configuration import ServerConfig
from xcap.uri import XCAPUri
from xcap.xcapdiff import Notifier


class OpensipsConfig(XCAPOpensipsConfig):
    outbound_sip_proxy = ConfigSetting(type=SIPProxyAddress, value=None)


@implementer(IObserver)
class SIPNotifier(object, metaclass=Singleton):

    def __init__(self):
        self.engine = Engine()
        self.engine.start(
            ip_address=None if ServerConfig.address == '0.0.0.0' else ServerConfig.address,
            tcp_port=ServerConfig.tcp_port,
            user_agent="OpenXCAP %s" % __version__,
        )
        self.sip_prefix_re = re.compile('^sips?:')
        try:
            outbound_sip_proxy = OpensipsConfig.outbound_sip_proxy
            self.outbound_proxy = SIPURI(host=outbound_sip_proxy.host,
                                         port=outbound_sip_proxy.port,
                                         parameters={'transport': 'tcp'})
        except ValueError:
            log.warning('Invalid SIP proxy address specified: %s' % OpensipsConfig.outbound_sip_proxy)
            self.outbound_proxy = None
        NotificationCenter().add_observer(self)

    @run_in_green_thread
    def send_publish(self, uri, body=None):
        if self.outbound_proxy is None or body is None:
            return

        self.body = body
        self.uri = self.sip_prefix_re.sub('', uri)
        lookup = DNSLookup()
        NotificationCenter().add_observer(self, sender=lookup)
        lookup.lookup_sip_proxy(self.outbound_proxy, ["udp", "tcp", "tls"])

    def handle_notification(self, notification: Notification) -> None:
        handler = getattr(self, '_NH_%s' % notification.name, Null)
        handler(notification)

    def _NH_DNSLookupDidSucceed(self, notification: Notification) -> None:
        notification_center = NotificationCenter()
        notification_center.remove_observer(self, sender=notification.sender)

        publication = Publication(FromHeader(SIPURI(self.uri)),
                                  "xcap-diff",
                                  "application/xcap-diff+xml",
                                  duration=0,
                                  extra_headers=[Header('Thor-Scope', 'publish-xcap')])
        notification_center.add_observer(self, sender=publication)
        route = notification.data.result[0]
        route_header = RouteHeader(route.uri)
        publication.publish(self.body, route_header, timeout=5)

    def _NH_DNSLookupDidFail(self, notification: Notification) -> None:
        notification.center.remove_observer(self, sender=notification.sender)

    def _NH_SIPPublicationDidSucceed(self, notification: Notification) -> None:
        log.info('PUBLISH for xcap-diff event successfully sent to %s for %s' % (notification.data.route_header.uri, notification.sender.from_header.uri))

    def _NH_SIPPublicationDidEnd(self, notification: Notification) -> None:
        log.info('PUBLISH for xcap-diff event ended for %s' % notification.sender.from_header.uri)
        notification.center.remove_observer(self, sender=notification.sender)

    def _NH_SIPPublicationDidFail(self, notification: Notification) -> None:
        log.info('PUBLISH for xcap-diff event failed to %s for %s' % (notification.data.route_header.uri, notification.sender.from_header.uri))
        notification.center.remove_observer(self, sender=notification.sender)


class NotifyingStorage(DatabaseStorage):
    def __init__(self):
        super(NotifyingStorage, self).__init__()
        self._sip_notifier = SIPNotifier()
        self.notifier = Notifier(ServerConfig.root, self._sip_notifier.send_publish)

    async def put_document(self, uri: XCAPUri, document: bytes, check_etag: Callable) -> Optional[StatusResponse]:
        result = await super(NotifyingStorage, self).put_document(uri, document, check_etag)
        if result and result.succeed:
            result.background = BackgroundTask(self.notifier.on_change, uri, result.old_etag, result.etag)
        return result

    async def delete_document(self, uri: XCAPUri, check_etag: Callable) -> Optional[StatusResponse]:
        result = await super(NotifyingStorage, self).delete_document(uri, check_etag)
        if result and result.succeed:
            result.background = BackgroundTask(self.notifier.on_change, uri, result.old_etag, None)
        return result


PasswordChecker = PasswordChecker

Storage: Union[type[DatabaseStorage], type[NotifyingStorage]] = DatabaseStorage

if OpensipsConfig.publish_xcapdiff:
    Storage = NotifyingStorage

installSignalHandlers = False
