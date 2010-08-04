
# Copyright (C) 2007-2010 AG Projects.
#

"""HTTP handling for the XCAP server"""

import sys

from application.configuration.datatypes import NetworkRangeList
from application.configuration import ConfigSection, ConfigSetting
from application import log

from twisted.web2 import channel, resource, http, responsecode, http_headers, server
from twisted.cred.portal import Portal
from twisted.web2.auth import basic
from xcap.tweaks import tweak_DigestCredentialFactory
from twisted.python import failure

import xcap
from xcap import authentication
from xcap.datatypes import XCAPRootURI
from xcap.appusage import getApplicationForURI, Backend
from xcap.resource import XCAPDocument, XCAPElement, XCAPAttribute, XCAPNamespaceBinding
from xcap.uri import AttributeSelector, NamespaceSelector, get_port_from_root_uri
from xcap.logutil import log_access, log_error
from xcap.tls import Certificate, PrivateKey

server.VERSION = "OpenXCAP/%s" % xcap.__version__
listen_port = None

class AuthenticationConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Authentication'

    type = 'digest'
    cleartext_passwords = True
    default_realm = ConfigSetting(type=str, value=None)
    trusted_peers = ConfigSetting(type=NetworkRangeList, value=NetworkRangeList('none'))

class ServerConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Server'

    address = '0.0.0.0'
    port = 0
    root = ConfigSetting(type=XCAPRootURI, value=None)
    backend = ConfigSetting(type=Backend, value=None)

class TLSConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'TLS'

    certificate = ConfigSetting(type=Certificate, value=None)
    private_key = ConfigSetting(type=PrivateKey, value=None)

if ServerConfig.root is None:
    log.fatal("the XCAP root URI is not defined")
    sys.exit(1)

if ServerConfig.backend is None:
    log.fatal("OpenXCAP needs a backend to be specified in order to run")
    sys.exit(1)

if ServerConfig.port:
    log.warn("Port setting is deprecated, please specify the port in the root setting")

listen_port = get_port_from_root_uri(ServerConfig.root)
if listen_port:
    for uri in ServerConfig.root.aliases:
        if get_port_from_root_uri(uri) != listen_port:
            log.fatal("Port needs to be the same in all aliases")
            sys.exit(1)
else:
    log.fatal("Invalid port specified")
    sys.exit(1)

class XCAPRoot(resource.Resource, resource.LeafResource):
    addSlash = True

    def allowedMethods(self):
        # not used , but methods were already checked by XCAPAuthResource
        return ('GET', 'PUT', 'DELETE')

    def resourceForURI(self, xcap_uri):
        application = getApplicationForURI(xcap_uri)
        if not xcap_uri.node_selector:
            return XCAPDocument(xcap_uri, application)
        else:
            terminal_selector = xcap_uri.node_selector.terminal_selector
            if isinstance(terminal_selector, AttributeSelector):
                return XCAPAttribute(xcap_uri, application)
            elif isinstance(terminal_selector, NamespaceSelector):
                return XCAPNamespaceBinding(xcap_uri, application)
            else:
                return XCAPElement(xcap_uri, application)

    def renderHTTP(self, request):
        application = getApplicationForURI(request.xcap_uri)
        if not application:
            return http.Response(responsecode.NOT_FOUND, stream="Application not supported")
        resource = self.resourceForURI(request.xcap_uri)
        return resource.renderHTTP(request)


def get_response_body(exc):
    if hasattr(exc, 'stream') and hasattr(exc.stream, 'mem'):
        return exc.stream.mem
    else:
        return str(exc)

class Request(server.Request):

    def __init__(self, *args, **kw):
        server.Request.__init__(self, *args, **kw)

    def writeResponse(self, response):
        reason = getattr(self, '_reason', None)
        log_access(self, response, reason)
        try:
            return server.Request.writeResponse(self, response)
        finally:
            if reason is not None:
                del self._reason

    def _processingFailed(self, reason):
        # save the reason, it will be used for the stacktrace
        self._reason = reason

        exc = getattr(reason, 'value', None)
        if exc:
            # if the exception has 'http_error' and it is HTTPError, we use it to generate the response.
            # this allows us to attach http_error to non-HTTPError errors (as opposed to
            # re-raising HTTPError-derived exception) and enjoy the original stacktraces in the log
            if not isinstance(exc, http.HTTPError) and hasattr(exc, 'http_error'):
                http_error = exc.http_error
                if isinstance(http_error, http.HTTPError):
                    return server.Request._processingFailed(self, failure.Failure(http_error))
                elif isinstance(http_error, int):
                    s = get_response_body(exc)
                    response = http.Response(http_error,
                                             {'content-type': http_headers.MimeType('text','plain')},
                                             stream=s)
                    fail = failure.Failure(http.HTTPError(response))
                    return server.Request._processingFailed(self, fail)

        return server.Request._processingFailed(self, reason)

    def renderHTTP_exception(self, req, reason):
        response = http.Response(
            responsecode.INTERNAL_SERVER_ERROR,
            {'content-type': http_headers.MimeType('text','plain')},
            ("An error occurred while processing the request. "
             "More information is available in the server log."))

        log_error(req, response, reason)
        return response


class HTTPChannelRequest(channel.http.HTTPChannelRequest):
    _base = channel.http.HTTPChannelRequest

    def gotInitialLine(self, line):
        self._initial_line = line
        return self._base.gotInitialLine(self, line)

    def createRequest(self):
        self._base.createRequest(self)
        self.request._initial_line = self._initial_line


class HTTPChannel(channel.http.HTTPChannel):
    chanRequestFactory = HTTPChannelRequest


class HTTPFactory(channel.HTTPFactory):
    noisy = False
    protocol = HTTPChannel


class XCAPSite(server.Site):

    def __call__(self, *args, **kwargs):
        return Request(site=self, *args, **kwargs)


class XCAPServer(object):
    global listen_port

    def __init__(self):
        portal = Portal(authentication.XCAPAuthRealm())
        if AuthenticationConfig.cleartext_passwords:
            http_checker = ServerConfig.backend.PlainPasswordChecker()
        else:
            http_checker = ServerConfig.backend.HashPasswordChecker()
        portal.registerChecker(http_checker)
        trusted_peers = AuthenticationConfig.trusted_peers
        portal.registerChecker(authentication.TrustedPeerChecker(trusted_peers))
        portal.registerChecker(authentication.PublicGetApplicationChecker())

        auth_type = AuthenticationConfig.type
        if auth_type == 'basic':
            credential_factory = basic.BasicCredentialFactory(auth_type)
        elif auth_type == 'digest':
            credential_factory = tweak_DigestCredentialFactory('MD5', auth_type)
        else:
            raise ValueError("Invalid authentication type: '%s'. Please check the configuration." % auth_type)

        root = authentication.XCAPAuthResource(XCAPRoot(),
                                               (credential_factory,),
                                               portal, (authentication.IAuthUser,))
        self.site = XCAPSite(root)

    def _start_https(self, reactor):
        from gnutls.interfaces.twisted import X509Credentials
        cert, pKey = TLSConfig.certificate, TLSConfig.private_key
        if cert is None or pKey is None:
            log.fatal("the TLS certificates or the private key could not be loaded")
            sys.exit(1)
        credentials = X509Credentials(cert, pKey)
        reactor.listenTLS(listen_port, HTTPFactory(self.site), credentials, interface=ServerConfig.address)
        log.msg("TLS started")

    def start(self):
        if 'twisted.internet.reactor' not in sys.modules:
            for name in ('epollreactor', 'kqreactor', 'pollreactor', 'selectreactor'):
                try:    __import__('twisted.internet.%s' % name, globals(), locals(), fromlist=[name]).install()
                except: continue
                else:   break
        from twisted.internet import reactor

        log.msg("Listening on: %s:%d" % (ServerConfig.address, listen_port))
        log.msg("XCAP root: %s" % ServerConfig.root)
        if ServerConfig.root.startswith('https'):
            self._start_https(reactor)
        else:
            reactor.listenTCP(listen_port, HTTPFactory(self.site), interface=ServerConfig.address)
        self.run(reactor)

    def run(self, reactor):
        reactor.run(installSignalHandlers=ServerConfig.backend.installSignalHandlers)

