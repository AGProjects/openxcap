
# Copyright (c) 2007-2010 AG Projects. See LICENSE for details.
#

"""Configuration data types"""

import re
import urlparse
from application import log

class XCAPRootURI(str):
    """An XCAP root URI and a number of optional aliases"""

    def __new__(cls, value):
        if value is None:
            return None
        elif not isinstance(value, basestring):
            raise TypeError("value must be a string, unicode or None")
        if value.strip() == '':
            return None
        valid_uris = []
        for uri in re.split(r'\s*,\s*', value):
            scheme, host, path, params, query, fragment = urlparse.urlparse(uri)
            if host and scheme in ('http', 'https'):
                for u in valid_uris:
                    if u == uri or uri.startswith(u) or u.startswith(uri):
                        log.warn("ignoring XCAP Root URI %r (similar to %r)" % (uri, u))
                        break
                else:
                    valid_uris.append(uri)
            else:
                log.warn("Invalid XCAP Root URI: %r" % uri)
        if not valid_uris:
            return None
        instance = str.__new__(cls, valid_uris[0])
        instance.uris = tuple(valid_uris)
        return instance

    def _get_port_from_uri(self, uri):
        scheme, netloc, path, params, query, fragment = urlparse.urlparse(uri)
        if scheme and netloc:
            if len(netloc.split(":")) == 2:
                try:
                    port = int(netloc.split(":")[1])
                except ValueError:
                    return None
                else:
                    return port if port < 65536 else None
            if scheme.lower() == "http":
                return 80
            if scheme.lower() == "https":
                return 443
        return None

    @property
    def aliases(self):
        return self.uris[1:]

    @property
    def port(self):
        listen_port = self._get_port_from_uri(self)
        if listen_port:
            for uri in self.aliases:
                if self._get_port_from_uri(uri) != listen_port:
                    raise ValueError("All XCAP root aliases must have the same port number")
            return listen_port
        else:
            raise ValueError("Invalid port specified")

