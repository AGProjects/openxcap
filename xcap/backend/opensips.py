
"""Implementation of an OpenSIPS backend."""

import re

from application import log
from application.configuration import ConfigSection, ConfigSetting
from application.configuration.datatypes import IPAddress
from application.notification import IObserver, NotificationCenter
from application.python import Null
from application.python.types import Singleton
from sipsimple.core import Engine, FromHeader, Header, Publication, RouteHeader, SIPURI
from sipsimple.configuration.datatypes import SIPProxyAddress
from sipsimple.threading import run_in_twisted_thread
from zope.interface import implements

import xcap
from xcap.datatypes import XCAPRootURI
from xcap.backend import database
from xcap.xcapdiff import Notifier


class ServerConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Server'

    address = ConfigSetting(type=IPAddress, value='0.0.0.0')
    root = ConfigSetting(type=XCAPRootURI, value=None)


class Config(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'OpenSIPS'

    publish_xcapdiff = False
    outbound_sip_proxy = ''


class PlainPasswordChecker(database.PlainPasswordChecker): pass
class HashPasswordChecker(database.HashPasswordChecker): pass


class SIPNotifier(object):
    __metaclass__ = Singleton

    implements(IObserver)

    def __init__(self):
        self.engine = Engine()
        self.engine.start(
           ip_address=None if ServerConfig.address == '0.0.0.0' else ServerConfig.address,
           user_agent="OpenXCAP %s" % xcap.__version__,
        )
        self.sip_prefix_re = re.compile('^sips?:')
        try:
            self.outbound_proxy = SIPProxyAddress.from_description(Config.outbound_sip_proxy)
        except ValueError:
            log.warning('Invalid SIP proxy address specified: %s' % Config.outbound_sip_proxy)
            self.outbound_proxy = None

    def send_publish(self, uri, body):
        if self.outbound_proxy is None:
            return
        uri = self.sip_prefix_re.sub('', uri)
        publication = Publication(FromHeader(SIPURI(uri)),
                                  "xcap-diff",
                                  "application/xcap-diff+xml",
                                  duration=0,
                                  extra_headers=[Header('Thor-Scope', 'publish-xcap')])
        NotificationCenter().add_observer(self, sender=publication)
        route_header = RouteHeader(SIPURI(host=self.outbound_proxy.host, port=self.outbound_proxy.port, parameters=dict(transport=self.outbound_proxy.transport)))
        publication.publish(body, route_header, timeout=5)

    @run_in_twisted_thread
    def handle_notification(self, notification):
        handler = getattr(self, '_NH_%s' % notification.name, Null)
        handler(notification)

    def _NH_SIPPublicationDidSucceed(self, notification):
        log.info('PUBLISH for xcap-diff event successfully sent to %s for %s' % (notification.data.route_header.uri, notification.sender.from_header.uri))

    def _NH_SIPPublicationDidEnd(self, notification):
        log.info('PUBLISH for xcap-diff event ended for %s' % notification.sender.from_header.uri)
        notification.center.remove_observer(self, sender=notification.sender)

    def _NH_SIPPublicationDidFail(self, notification):
        log.info('PUBLISH for xcap-diff event failed to %s for %s' % (notification.data.route_header.uri, notification.sender.from_header.uri))
        notification.center.remove_observer(self, sender=notification.sender)


class NotifyingStorage(database.Storage):
    def __init__(self):
        super(NotifyingStorage, self).__init__()
        self._sip_notifier = SIPNotifier()
        self.notifier = Notifier(ServerConfig.root, self._sip_notifier.send_publish)

    def put_document(self, uri, document, check_etag):
        d = super(NotifyingStorage, self).put_document(uri, document, check_etag)
        d.addCallback(lambda result: self._on_put(result, uri))
        return d

    def _on_put(self, result, uri):
        if result.succeed:
            self.notifier.on_change(uri, result.old_etag, result.etag)
        return result

    def delete_document(self, uri, check_etag):
        d = super(NotifyingStorage, self).delete_document(uri, check_etag)
        d.addCallback(lambda result: self._on_delete(result, uri))
        return d

    def _on_delete(self, result, uri):
        if result.succeed:
            self.notifier.on_change(uri, result.old_etag, None)
        return result


if Config.publish_xcapdiff:
    Storage = NotifyingStorage
else:
    Storage = database.Storage

installSignalHandlers = database.installSignalHandlers
