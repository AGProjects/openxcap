# Copyright (C) 2007 AG Projects.
#

"""HTTP handling for the XCAP server"""

import sys
import os

from application.configuration.datatypes import StringList, NetworkRangeList
from application import log

from zope.interface import implements

if 'twisted.internet.reactor' not in sys.modules:
    from twisted.internet import pollreactor; pollreactor.install()

from twisted.internet import reactor
from twisted.web2 import channel, resource, http, responsecode, server
from twisted.cred.portal import Portal
from twisted.cred import credentials, portal, checkers, error as credError
from twisted.web2.auth import digest, basic, wrapper

from xcap.config import *
from xcap import authentication
from xcap.appusage import getApplicationForURI
from xcap.resource import XCAPDocument, XCAPElement, XCAPAttribute, XCAPNamespaceBinding
from xcap.tls import Certificate, PrivateKey
from xcap.uri import XCAPUri, AttributeSelector, NamespaceSelector
from xcap import __version__ as version

server.VERSION = "OpenXCAP/%s" % version

class Backend(object):
    """Configuration datatype, used to select a backend module from the configuration file."""
    def __new__(typ, value):
        try:
            return __import__('xcap.interfaces.backend.%s' % value.lower(), globals(), locals(), [''])
        except ImportError, e:
            raise ValueError("Couldn't find the '%s' backend module: %s" % (value.lower(), str(e)))

class AuthenticationConfig(ConfigSection):
    _datatypes = {'trusted_peers': StringList,
                  'default_realm': str}
    type = 'basic'
    cleartext_passwords = True
    default_realm = None
    trusted_peers = []

class ServerConfig(ConfigSection):
    _datatypes = {'backend': Backend}
    port = 8000
    address = '0.0.0.0'
    root = 'http://127.0.0.1/'
    backend = Backend('Database')

class TLSConfig(ConfigSection):
    _datatypes = {'certificate': Certificate, 'private_key': PrivateKey}
    certificate = None
    private_key = None

## We use this to overwrite some of the settings above on a local basis if needed
configuration = ConfigFile()
configuration.read_settings('Authentication', AuthenticationConfig)
configuration.read_settings('Server', ServerConfig)
configuration.read_settings('TLS', TLSConfig)


def log_request(request, response):
    uri = request.xcap_uri
    method = request.method
    user_agent = request.headers.getHeader('user-agent', 'unknown')
    size = 0
    if method == "GET" and response.stream is not None:
        size = response.stream.length
    elif method in ("PUT", "DELETE") and request.stream is not None:
        size = request.stream.length
    log_uri = "%s://%s:%d%s" % (request.scheme, request.host, request.port, request.uri)
    msg = '%s from %s "%s %s" %s %d - %s' % (uri.user, request.remoteAddr.host,
                                        method, log_uri, response.code, size, user_agent)
    log.msg(msg)


class XCAPRoot(resource.Resource, resource.LeafResource):
    addSlash = True

    def allowedMethods(self):
        return ('GET', 'PUT', 'DELETE')

    def resourceForURI(self, xcap_uri):
        application = getApplicationForURI(xcap_uri)
        if not xcap_uri.node_selector: ## the request is for an XCAP document
            return XCAPDocument(xcap_uri, application)
        else:
            terminal_selector = xcap_uri.node_selector.terminal_selector
            if isinstance(terminal_selector, AttributeSelector):
                return XCAPAttribute(xcap_uri, application)
            elif isinstance(terminal_selector, NamespaceSelector):
                return XCAPNamespaceBinding(xcap_uri, application)
            else: ## the request is for an element
                return XCAPElement(xcap_uri, application)

    def cbLogRequest(self, response, request):
        try:
            log_request(request, response)
        except Exception, e:
            log.error("Error while logging XCAP request: %s" % str(e))
            log.err()
        return response

    def renderHTTP(self, request):
        ## forward the request to the appropiate XCAP resource, based on the 
        ## XCAP request URI
        xcap_uri = request.xcap_uri
        application = getApplicationForURI(xcap_uri)
        if not application:
            return http.Response(responsecode.NOT_FOUND, stream="Application not supported")
        resource = self.resourceForURI(xcap_uri) ## let the appropriate resource handle the request
        d = resource.renderHTTP(request)
        d.addCallback(self.cbLogRequest, request)
        return d


class XCAPServer:
    
    def __init__(self):
        portal = Portal(authentication.XCAPAuthRealm())
        if AuthenticationConfig.cleartext_passwords:
            http_checker = ServerConfig.backend.PlainPasswordChecker()
        else:
            http_checker = ServerConfig.backend.HashPasswordChecker()
        portal.registerChecker(http_checker)
        trusted_peers = AuthenticationConfig.trusted_peers
        if trusted_peers:
            log.info("Trusted peers: %s" % ", ".join(trusted_peers))
        portal.registerChecker(authentication.TrustedPeerChecker(trusted_peers))

        auth_type = AuthenticationConfig.type
        if auth_type == 'basic':
            credential_factory = basic.BasicCredentialFactory(auth_type)
        elif auth_type == 'digest':
            credential_factory = digest.DigestCredentialFactory('MD5', auth_type)
        else:
            raise ValueError("Invalid authentication type: '%s'. Please check the configuration." % auth_type)

        root = authentication.XCAPAuthResource(XCAPRoot(),
                                            (credential_factory,),
                                            portal, (authentication.IAuthUser,))
        self.site = server.Site(root)

    def start(self):
        channel.HTTPFactory.noisy = False
        if ServerConfig.root.startswith('https'):
            from gnutls.interfaces.twisted import X509Credentials
            cert, pKey = TLSConfig.certificate, TLSConfig.private_key
            if cert is None or pKey is None:
                log.fatal("the TLS certificates or the private key could not be loaded")
            credentials = X509Credentials(cert, pKey)
            reactor.listenTLS(ServerConfig.port, channel.HTTPFactory(self.site), credentials, interface=ServerConfig.address)
            log.msg("TLS started")
        else:        
            reactor.listenTCP(ServerConfig.port, channel.HTTPFactory(self.site), interface=ServerConfig.address)
        reactor.run(installSignalHandlers=ServerConfig.backend.installSignalHandlers)
