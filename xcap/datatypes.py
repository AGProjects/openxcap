
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
                    if u==uri or uri.startswith(u) or u.startswith(uri):
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

    @property
    def aliases(self):
        return self.uris[1:]

