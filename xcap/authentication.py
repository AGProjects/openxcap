# Copyright (C) 2007 AG Projects.
#

"""XCAP authentication module"""

from zope.interface import Interface, implements

from twisted.internet import defer
from twisted.python import failure
from twisted.cred import credentials, portal, checkers, error as credError
from twisted.enterprise import adbapi, util as dbutil
from twisted.web2 import http, server, stream
from twisted.web2.auth.wrapper import HTTPAuthResource, UnauthorizedResponse

from application.configuration import readSettings, ConfigSection
from application.configuration.datatypes import StringList, NetworkRangeList
from application import log

from xcap.appusage import getApplicationForURI
from xcap.dbutil import connectionForURI
from xcap.errors import ResourceNotFound
from xcap.uri import XCAPUser, parseNodeURI

class ServerConfig(ConfigSection):
    _dataTypes = {'trusted_peers': StringList}
    trusted_peers = []

class AuthenticationConfig(ConfigSection):
    default_realm = 'example.com'

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('Authentication', AuthenticationConfig)
readSettings('Server', ServerConfig)

## Trusted Peer credentials

class TrustedPeerCredentials:
    implements(credentials.ICredentials)

    def __init__(self, peer):
        self.peer = peer

    def checkPeer(self, trusted_peers):
        return self.peer in trusted_peers

## credentials checkers

class TrustedPeerChecker:

    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.ICredentials,)

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
        request.xcap_uri = parseNodeURI(uri, AuthenticationConfig.default_realm)
        ## For each request the authentication realm must be
        ## dinamically deducted from the XCAP request URI
        realm = request.xcap_uri.user.domain
        self._updateRealm(realm)
        remote_addr = request.remoteAddr.host
        if ServerConfig.trusted_peers:
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

        if interface is IAuthUser and application.is_authorized(XCAPUser(avatar_id), xcap_uri):
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
        def _renderResource(resource):
            return resource.renderHTTP(request)

        def _finished_reading(ignore, result):
            data = ''.join(result)
            request.attachment = data
            d = self.authenticate(request)
            d.addCallback(_renderResource)
            return d
        def _failed_reading(failure):
            log.error('PUT: failed reading : ', str(failure))
            return http.Response(responsecode.INTERNAL_SERVER_ERROR, stream="Could not read data")

        if request.method in ('PUT', 'DELETE'):
            # we need to authenticate the request after all the attachment stream
            # has been read
            data = []
            d = stream.readStream(request.stream, data.append)
            d.addCallbacks(_finished_reading, _failed_reading, callbackArgs=(data,))
            return d
        else:
            d = self.authenticate(request)
            d.addCallback(_renderResource)

        return d
