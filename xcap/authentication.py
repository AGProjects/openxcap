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
from application import log

from xcap.appusage import getApplicationForURI
from xcap.dbutil import connectionForURI
from xcap.errors import ResourceNotFound
from xcap.uri import parseNodeURI


class AuthenticationConfig(ConfigSection):
    default_realm = 'example.com'
    db_uri = 'mysql://user:pass@db/openser'

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('Authentication', AuthenticationConfig)

## credentials checkers


class DatabasePasswordChecker:
    """A credentials checker against a database subscriber table."""

    implements(checkers.ICredentialsChecker)

    credentialInterfaces = (credentials.IUsernamePassword,
        credentials.IUsernameHashedPassword)

    def __init__(self):
        self.__db_connect()

    def __db_connect(self):
        self.conn = connectionForURI(AuthenticationConfig.db_uri)

    def _query_credentials(self, credentials):
        raise NotImplementedError

    def _got_query_results(self, rows, credentials):
        if not rows:
            raise credError.UnauthorizedLogin("Unauthorized login")
        else:
            return self._authenticate_credentials(rows[0][0], credentials)

    def _authenticate_credentials(self, password, credentials):
        raise NotImplementedError

    def _checkedPassword(self, matched, username, realm):
        if matched:
            username = username.split('@', 1)[0]
            ## this is the avatar ID
            return "%s@%s" % (username, realm)
        else:
            raise credError.UnauthorizedLogin("Unauthorized login")

    def requestAvatarId(self, credentials):
        """Return the avatar ID for the credentials which must have the username 
           and realm attributes, or an UnauthorizedLogin in case of a failure."""
        d = self._query_credentials(credentials)
        return d


class PlainDatabasePasswordChecker(DatabasePasswordChecker):
    """A credentials checker against a database subscriber table."""

    implements(checkers.ICredentialsChecker)

    def _query_credentials(self, credentials):
        username, domain = credentials.username.split('@', 1)[0], credentials.realm
        quote = dbutil.quote
        query = """SELECT password
                   FROM subscriber 
                   WHERE username = %(username)s AND domain = %(domain)s""" % {
                    "username": quote(username, "char"), 
                    "domain":   quote(domain, "char")}
        return self.conn.runQuery(query).addCallback(self._got_query_results, credentials)

    def _authenticate_credentials(self, hash, credentials):
        return defer.maybeDeferred(
                credentials.checkPassword, hash).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)


class HashDatabasePasswordChecker(DatabasePasswordChecker):
    """A credentials checker against a database subscriber table."""

    implements(checkers.ICredentialsChecker)

    def _query_credentials(self, credentials):
        username, domain = credentials.username.split('@', 1)[0], credentials.realm
        quote = dbutil.quote
        query = """SELECT ha1 
                   FROM subscriber 
                   WHERE username = %(username)s AND domain = %(domain)s""" % {
                    "username": quote(username, "char"), 
                    "domain":   quote(domain, "char")}
        return self.conn.runQuery(query).addCallback(self._got_query_results, credentials)

    def _authenticate_credentials(self, hash, credentials):
        return defer.maybeDeferred(
                credentials.checkHash, hash).addCallback(
                self._checkedPassword, credentials.username, credentials.realm)

## avatars

class IXCAPUser(Interface):
    pass


class XCAPUser(object):     ## poate ar trebui definit ca username si realm
    """XCAP User avatar."""
    implements(IXCAPUser)

    def __init__(self, user_id): 
        if user_id.startswith("sip:"):
            user_id = user_id[4:]
        _split = user_id.split('@', 1)
        self.username = _split[0]
        if len(_split) == 2:
            self.domain = _split[1]
        else:
            self.domain = None

    def __eq__(self, other):
        return isinstance(other, XCAPUser) and self.username == other.username and self.domain == other.domain

    def __ne__(self, other):
        return not self.__eq__(other)

    def __nonzero__(self):
        return bool(self.username) and bool(self.domain)

    def __str__(self):
        return "%s@%s" % (self.username, self.domain)

## realm

class XCAPAuthRealm(object):
    """XCAP authentication realm. Receives an avatar ID ( a string identifying the user)
       and a list of interfaces the avatar needs to support. It returns an avatar that
       encapsulates data about that user."""
    implements(portal.IRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IXCAPUser in interfaces:
            return IXCAPUser, XCAPUser(avatarId)

        raise NotImplementedError("Only IXCAPUser interface is supported")

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
        return HTTPAuthResource.authenticate(self, request)

    def _loginSucceeded(self, avatar, request):
        """Authorizes an XCAP request after it has been authenticated."""
        
        avatarInterface, xcap_user = avatar ## the avatar is the authenticated XCAP User
        xcap_uri = request.xcap_uri

        application = getApplicationForURI(xcap_uri)

        if not application:
            raise ResourceNotFound

        if application and application.is_authorized(xcap_user, xcap_uri):
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

        if request.method in ('PUT', 'DELETE', 'POST'):
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
