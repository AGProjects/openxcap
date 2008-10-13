import urlparse
from application import log

from xcap.errors import ResourceNotFound
from xcap.config import ConfigFile

configuration = ConfigFile()

def list_contains_uri(uris, uri):
    for u in uris:
        if u == uri:
            return True
        if uri.startswith(u) or u.startswith(uri):
            log.warn("XCAP Root URI rejected: %r (looks like %r)" % (uri, u))
            return True

class XCAPRootURIs(tuple):
    """Configuration data type. A tuple of defined XCAP Root URIs is extracted from
       the configuration file."""
    def __new__(typ):
        uris = []
        def add(uri):
            scheme, host, path, params, query, fragment = urlparse.urlparse(uri)
            if not scheme or not host or scheme not in ("http", "https"):
                log.warn("Invalid XCAP Root URI: %r" % uri)
            elif not list_contains_uri(uris, uri):
                uris.append(uri)
        for uri in configuration.get_values_unique('Server', 'root'):
            add(uri)
        if not uris:
            import socket
            add('http://' + socket.getfqdn())
        if not uris:
            raise ResourceNotFound("At least one XCAP Root URI must be defined")
        return tuple(uris)

root_uris = XCAPRootURIs()
print 'Supported Root URIs: %s' % ', '.join(root_uris)
