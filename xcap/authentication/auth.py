import base64
import hashlib
import socket
import struct
import time
from typing import Dict, Optional
from uuid import uuid4

from fastapi import HTTPException, Request

from xcap import __version__
from xcap.appusage import ServerConfig as Backend
from xcap.appusage import namespaces, public_get_applications
from xcap.configuration import AuthenticationConfig, ServerConfig
from xcap.errors import ResourceNotFound
from xcap.http_utils import get_client_ip
from xcap.uri import XCAPUri
from xcap.xpath import DocumentSelectorError, NodeParsingError

# In-memory nonce cache with expiration time (for demonstration purposes)
nonce_cache: Dict[int, str] = {}
NONCE_EXPIRATION_TIME = 900  # 15 minutes for nonce expiration

WELCOME = ('<html><head><title>Not Found</title></head>'
           '<body><h1>Not Found</h1>XCAP server does not serve anything '
           'directly under XCAP Root URL. You have to be more specific.'
           '<br><br>'
           '<address><a href="http://www.openxcap.org">OpenXCAP/%s</address>'
           '</body></html>') % __version__


def parseNodeURI(node_uri: str, default_realm: str) -> XCAPUri:
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
    if not resource_selector or resource_selector == '/':
        raise ResourceNotFound(WELCOME, "text/html")

    try:
        r = XCAPUri(xcap_root, resource_selector, namespaces)
    except NodeParsingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.args)
    except DocumentSelectorError as e:
        raise HTTPException(status_code=e.status_code, detail=e.args)
    if r.user.domain is None:
        r.user.domain = default_realm
    return r


class Credentials(object):
    def __init__(self, username, password=None, realm=None):
        self.username = username
        self.password = password
        self.realm = realm

    @property
    def hash(self):
        return hashlib.md5('{0.username}:{0.realm}:{0.password}'.format(self).encode()).hexdigest()

    def checkPassword(self, password: bytes) -> bool:
        return self.password == password

    def checkHash(self, digestHash):
        return digestHash == self.hash

    def is_valid(self, user):
        if AuthenticationConfig.cleartext_passwords:
            return self.checkPassword(user.password)
        else:
            return self.checkHash(user.ha1)


class AuthenticationManager:
    def __init__(self):
        self.nonce_cache = nonce_cache
        self.trusted_peers = AuthenticationConfig.trusted_peers

    # Helper function to generate a nonce
    def generate_nonce(self) -> str:
        """Generate a new nonce (typically a random string with a timestamp)."""
        timestamp = int(time.time())
        unique_nonce = f"{timestamp}-{uuid4()}"
        return base64.b64encode(unique_nonce.encode()).decode("utf-8")

    # Helper function to create the Digest response hash
    async def create_digest_response(self, username: str, nonce: str, uri: str, method: str, realm: str, cnonce: str, nc: str, qop: str) -> str:
        credentials = Credentials(username.split('@', 1)[0], realm=realm)
        user = await Backend.backend.PasswordChecker().query_user(credentials)

        if user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        ha1 = user[0].ha1
        if AuthenticationConfig.cleartext_passwords:
            ha1 = credentials.hash

        # Compute the ha2 hash (method:uri)
        ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()

        # Compute the final response using the formula: MD5(HA1:nonce:nc:cnonce:qop:HA2)
        response = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()

        return response

    # Function to validate and clean up expired nonces
    def validate_nonce(self, nonce: str) -> bool:
        """Check if the nonce is valid and not expired."""
        if nonce not in self.nonce_cache:
            return False
        timestamp, _ = self.nonce_cache[nonce]
        current_time = int(time.time())
        if current_time - timestamp > NONCE_EXPIRATION_TIME:
            # Nonce expired, remove it from the cache
            del self.nonce_cache[nonce]
            return False
        return True

    # Digest Authentication Dependency
    async def digest_auth(self, request: Request, realm: str) -> None:
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Digest "):
            nonce = self.generate_nonce()
            opaque = "eee38d7sacbefv2a3450ciny7QMkPqMAFRtzCUYo5tdS"

            self.nonce_cache[nonce] = (int(time.time()), opaque)  # Store nonce with timestamp
            www_authenticate_header = (
                f'Digest realm="{realm}", nonce="{nonce}", opaque={opaque}, algorithm=MD5, qop=auth'
            )
            raise HTTPException(
                status_code=401,
                detail="Digest authentication required",
                headers={"WWW-Authenticate": www_authenticate_header},
            )

        # Parse the Digest fields from the header
        try:
            auth_fields = {k: v.strip('"') for k, v in (field.split("=", 1) for field in auth_header[7:].split(", "))}
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid Digest authentication format")

        required_fields = ["username", "nonce", "response", "uri", "qop", "cnonce", "nc"]
        for field in required_fields:
            if field not in auth_fields:
                raise HTTPException(status_code=401, detail=f"Missing required Digest field: {field}")

        username = auth_fields["username"]
        nonce = auth_fields["nonce"]
        response = auth_fields["response"]
        uri = auth_fields['uri']
        method = request.method
        cnonce = auth_fields['cnonce']
        nc = auth_fields['nc']
        qop = auth_fields['qop']

        # Use the database session to check for user
        if not self.validate_nonce(nonce):
            raise HTTPException(status_code=401, detail="Invalid or expired nonce")

        # Validate the Digest response
        expected_response = await self.create_digest_response(username, nonce, uri, method, realm, cnonce, nc, qop)
        # expected_response = self.create_digest_response(username, nonce, uri, method, db, realm)

        if response != expected_response:
            raise HTTPException(status_code=401, detail="Invalid credentials or response")

    async def basic_auth(self, request: Request, realm: str) -> None:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Basic "):
            raise HTTPException(
                status_code=401,
                detail="Basic authentication required",
                headers={"WWW-Authenticate": f"Basic realm=\"{AuthenticationConfig.default_realm}\""}
            )

        auth_value = auth_header[6:].strip()
        decoded_value = base64.b64decode(auth_value).decode("utf-8")
        username, password = decoded_value.split(":")
        credentials = Credentials(username, password, realm)

        user = await Backend.backend.PasswordChecker().query_user(credentials)

        if user is None or not credentials.is_valid(user[0]):
            raise HTTPException(
                status_code=401,
                detail="Invalid credentials"
            )

    # Function to check if the client IP is in the trusted peers list
    def is_ip_trusted(self, client_ip: Optional[str]) -> bool:
        """Check if the client IP is in the trusted peers list."""
        if not self.trusted_peers or client_ip is None:
            return False

        # Iterate through each network range in the trusted_parties list
        for range in self.trusted_peers:
            # Convert the IP address to a 32-bit integer
            ip_int = struct.unpack('!L', socket.inet_aton(client_ip))[0]

            # Perform the bitwise comparison (IP address & network mask == base address)
            if ip_int & range[1] == range[0]:
                return True

        # If the IP address does not match any range, return False
        return False

    async def authenticate_request(self, request: Request) -> XCAPUri:
        """Authenticate a request by checking IP and applying Digest or Basic authentication as needed."""
        client_ip = get_client_ip(request)
        xcap_uri = parseNodeURI(str(request.url), AuthenticationConfig.default_realm)

        if xcap_uri.doc_selector.context == 'global':
            return xcap_uri

        realm = xcap_uri.user.domain

        if realm is None:
            raise ResourceNotFound('Unknown domain (the domain part of "username@domain" is required because this server has no default domain)')

        if request.method == "GET" and xcap_uri.application_id in public_get_applications:
            return xcap_uri

        if self.is_ip_trusted(client_ip):
            return xcap_uri

        if AuthenticationConfig.type == 'digest':
            await self.digest_auth(request, realm)
        elif AuthenticationConfig.type == 'basic':
            await self.basic_auth(request, realm)
        else:
            raise ValueError('Invalid authentication type: %r. Please check the configuration.' % AuthenticationConfig.type)

        return xcap_uri
