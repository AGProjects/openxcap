# Copyright (C) 2007 AG Projects.
#

"""XCAP authentication module"""

# XXX this module should be either renamed or refactored as it does more then just auth.

from xcap import tweaks; tweaks.tweak_BasicCredentialFactory()

from zope.interface import Interface, implements

from twisted.internet import defer
from twisted.python import failure
from twisted.cred import credentials, portal, checkers, error as credError
from twisted.web2 import http, server, stream, responsecode, http_headers
from twisted.web2.auth.wrapper import HTTPAuthResource, UnauthorizedResponse

from application.configuration.datatypes import NetworkRangeList, NetworkRange
from application.configuration import ConfigSection, ConfigSetting

import struct
import socket

import xcap
from xcap.datatypes import XCAPRootURI
from xcap.appusage import getApplicationForURI, namespaces
from xcap.errors import ResourceNotFound
from xcap.uri import XCAPUser, XCAPUri


# body of 404 error message to render when user requests xcap-root
# it's html, because XCAP root is often published on the web.
# NOTE: there're no plans to convert other error messages to html.
# Since a web-browser is not the primary tool for accessing XCAP server, text/plain
# is easier for clients to present to user/save to logs/etc.
WELCOME = ('<html><head><title>Not Found</title></head>'
           '<body><h1>Not Found</h1>XCAP server does not serve anything '
           'directly under XCAP Root URL. You have to be more specific.'
           '<br><br>'
           '<address><a href="http://www.openxcap.org">OpenXCAP/%s</address>'
           '</body></html>') % xcap.__version__


class AuthenticationConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Authentication'

    default_realm = ConfigSetting(type=str, value=None)
    trusted_peers = ConfigSetting(type=NetworkRangeList, value=NetworkRangeList('none'))

if AuthenticationConfig.trusted_peers is None:
    AuthenticationConfig.trusted_peers = [NetworkRange('none')]

class ServerConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Server'

    root = ConfigSetting(type=XCAPRootURI, value=None)


def generateWWWAuthenticate(headers):
    _generated = []
    for seq in headers:
        scheme, challenge = seq[0], seq[1]

        # If we're going to parse out to something other than a dict
        # we need to be able to generate from something other than a dict

        try:
            l = []
            for k,v in dict(challenge).iteritems():
                l.append("%s=%s" % (k, k in ("algorithm", "stale") and v or http_headers.quoteString(v)))

            _generated.append("%s %s" % (scheme, ", ".join(l)))
        except ValueError:
            _generated.append("%s %s" % (scheme, challenge))

    return _generated

http_headers.generator_response_headers["WWW-Authenticate"] = (generateWWWAuthenticate,)
http_headers.DefaultHTTPHandler.updateGenerators(http_headers.generator_response_headers)
del generateWWWAuthenticate

def parseNodeURI(node_uri, default_realm):
    """Parses the given Node URI, containing the XCAP root, document selector,
       and node selector, and returns an XCAPUri instance if succesful."""
    xcap_root = None
    for uri in ServerConfig.root.uris:
        if node_uri.startswith(uri):
            xcap_root = uri
            break
    if xcap_root is None:
        raise ResourceNotFound("XCAP root not found for URI: %s" % node_uri)
    resource_selector = node_uri[len(xcap_root):]
    if not resource_selector or resource_selector=='/':
        raise ResourceNotFound(WELCOME, http_headers.MimeType("text", "html"))
    r = XCAPUri(xcap_root, resource_selector, namespaces)
    if r.user.domain is None:
        r.user.domain = default_realm
    return r


class ITrustedPeerCredentials(credentials.ICredentials):

    def checkPeer(self, trusted_peers):
        pass


class TrustedPeerCredentials(object):
    implements(ITrustedPeerCredentials)

    def __init__(self, peer):
        self.peer = peer

    def checkPeer(self, trusted_peers):
        for range in trusted_peers:
            if struct.unpack('!L', socket.inet_aton(self.peer))[0] & range[1] == range[0]:
                return True
        return False

## credentials checkers

class TrustedPeerChecker(object):

    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (ITrustedPeerCredentials,)

    def __init__(self, trusted_peers):
        self.trusted_peers = trusted_peers

    def requestAvatarId(self, credentials):
        """Return the avatar ID for the credentials which must have a 'peer' attribute,
           or an UnauthorizedLogin in case of a failure."""
        if credentials.checkPeer(self.trusted_peers):
            return defer.succeed(credentials.peer)
        return defer.fail(credError.UnauthorizedLogin())

## avatars

class IAuthUser(Interface):
    pass

class ITrustedPeer(Interface):
    pass

class AuthUser(str):
    """Authenticated XCAP User avatar."""
    implements(IAuthUser)

class TrustedPeer(str):
    """Trusted peer avatar."""
    implements(ITrustedPeer)

## realm

class XCAPAuthRealm(object):
    """XCAP authentication realm. Receives an avatar ID (a string identifying the user)
       and a list of interfaces the avatar needs to support. It returns an avatar that
       encapsulates data about that user."""
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IAuthUser in interfaces:
            return IAuthUser, AuthUser(avatarId)
        elif ITrustedPeer in interfaces:
            return ITrustedPeer, TrustedPeer(avatarId)

        raise NotImplementedError("Only IAuthUser and ITrustedPeer interfaces are supported")

def get_cred(request, default_realm):
    auth = request.headers.getHeader('authorization')
    if auth:
        typ, data = auth
        if typ == 'basic':
            return data.decode('base64').split(':', 1)[0], default_realm
        elif typ == 'digest':
            raise NotImplementedError
    return None, default_realm

## authentication wrapper for XCAP resources
class XCAPAuthResource(HTTPAuthResource):

    def allowedMethods(self):
        return ('GET', 'PUT', 'DELETE')

    def _updateRealm(self, realm):
        """Updates the realm of the attached credential factories."""
        for factory in self.credentialFactories.values():
            factory.realm = realm

    def authenticate(self, request):
        """Authenticates an XCAP request."""
        uri = request.scheme + "://" + request.host + request.uri
        xcap_uri = parseNodeURI(uri, AuthenticationConfig.default_realm)
        request.xcap_uri = xcap_uri
        if xcap_uri.doc_selector.context=='global':
            return defer.succeed(self.wrappedResource)

        ## For each request the authentication realm must be
        ## dinamically deducted from the XCAP request URI
        realm = xcap_uri.user.domain

        if realm is None:
            raise ResourceNotFound('Unknown domain (the domain part of "username@domain" is required because this server has no default domain)')

        if not xcap_uri.user.username:
            # for 'global' requests there's no username@domain in the URI,
            # so we will use username and domain from Authorization header
            xcap_uri.user.username, xcap_uri.user.domain = get_cred(request, AuthenticationConfig.default_realm)

        self._updateRealm(realm)
        remote_addr = request.remoteAddr.host
        if AuthenticationConfig.trusted_peers:
            return self.portal.login(TrustedPeerCredentials(remote_addr),
                                     None,
                                     ITrustedPeer
                                     ).addCallbacks(self._loginSucceeded,
                                                    self._trustedPeerLoginFailed,
                                                    (request,), None,
                                                    (request,), None)
        return HTTPAuthResource.authenticate(self, request)

    def _trustedPeerLoginFailed(self, result, request):
        """If the peer is not trusted, fallback to HTTP basic/digest authentication."""
        return HTTPAuthResource.authenticate(self, request)

    def _loginSucceeded(self, avatar, request):
        """Authorizes an XCAP request after it has been authenticated."""
        
        interface, avatar_id = avatar ## the avatar is the authenticated XCAP User
        xcap_uri = request.xcap_uri

        application = getApplicationForURI(xcap_uri)

        if not application:
            raise ResourceNotFound

        if interface is IAuthUser and application.is_authorized(XCAPUser.parse(avatar_id), xcap_uri):
            return HTTPAuthResource._loginSucceeded(self, avatar, request)
        elif interface is ITrustedPeer:
            return HTTPAuthResource._loginSucceeded(self, avatar, request)
        else:
            return failure.Failure(
                      http.HTTPError(
                        UnauthorizedResponse(
                        self.credentialFactories,
                        request.remoteAddr)))

    def locateChild(self, request, seg):
        """
        Authenticate the request then return the C{self.wrappedResource}
        and the unmodified segments.
        We're not using path location, we want to fall back to the renderHTTP() call.
        """
        #return self.authenticate(request), seg
        return self, server.StopTraversal

    def renderHTTP(self, request):
        """
        Authenticate the request then return the result of calling renderHTTP
        on C{self.wrappedResource}
        """
        if request.method not in self.allowedMethods():
            response = http.Response(responsecode.NOT_ALLOWED)
            response.headers.setHeader("allow", self.allowedMethods())
            return response

        def _renderResource(resource):
            return resource.renderHTTP(request)

        def _finished_reading(ignore, result):
            data = ''.join(result)
            request.attachment = data
            d = self.authenticate(request)
            d.addCallback(_renderResource)
            return d

        if request.method in ('PUT', 'DELETE'):
            # we need to authenticate the request after all the attachment stream
            # has been read
            # QQQ DELETE doesn't have any attachments, does it? nor does GET.
            # QQQ Reading attachment when there isn't one won't hurt, will it?
            # QQQ So why don't we just do it all the time for all requests?
            data = []
            d = stream.readStream(request.stream, data.append)
            d.addCallback(_finished_reading, data)
            return d
        else:
            d = self.authenticate(request)
            d.addCallback(_renderResource)

        return d
