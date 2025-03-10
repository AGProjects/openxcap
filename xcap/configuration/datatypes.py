
"""Configuration data types"""
import os
import re
import urllib.parse
import sys
from application import log


class XCAPRootURI(str):
    """An XCAP root URI and a number of optional aliases"""

    def __new__(cls, value):
        if value is None:
            return None
        elif not isinstance(value, str):
            raise TypeError("value must be a string, unicode or None")
        if value.strip() == '':
            return None
        valid_uris = []
        for uri in re.split(r'\s*,\s*', value):
            scheme, host, path, params, query, fragment = urllib.parse.urlparse(uri)
            if host and scheme in ('http', 'https'):
                for u in valid_uris:
                    if u == uri or uri.startswith(u) or u.startswith(uri):
                        log.warning('Ignoring XCAP Root URI %r (similar to %r)' % (uri, u))
                        break
                else:
                    valid_uris.append(uri)
            else:
                log.warning('Invalid XCAP Root URI: %r' % uri)
        if not valid_uris:
            return None
        instance = str.__new__(cls, valid_uris[0])
        instance.uris = tuple(valid_uris)
        return instance

    def _get_port_from_uri(self, uri):
        scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(uri)
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


class DatabaseURI(str):
    """A database URI that automatically sets some default parameters if missing, based on scheme"""

    def __new__(cls, value):
        if isinstance(value, str):
            urllib.parse.uses_netloc.extend(['mysql', 'postgres', 'sqlite', 'sqlite+aiosqlite'])
            urllib.parse.uses_relative.extend(['sqlite', 'sqlite+aiosqlite', 'postgres'])
            dburi = urllib.parse.urlparse(value)
            # set appropriate defaults for mysql's charset and sqlite's timeout if not specified
            if dburi.scheme == 'mysql':
                dburi = dburi._replace(scheme='mysql+aiomysql')
            elif dburi.scheme == 'sqlite':
                dburi = dburi._replace(scheme='sqlite+aiosqlite')
            return super(DatabaseURI, cls).__new__(cls, urllib.parse.urlunparse(dburi))
        else:
            raise TypeError('value should be a string')


class Backend(object):
    """Configuration datatype, used to select a backend module from the configuration file."""
    def __new__(typ, value):
        value = value.lower()
        try:
            return __import__('xcap.backend.%s' % value, globals(), locals(), [''])
        except (ImportError, AssertionError) as e:
            log.critical('Cannot load %r backend module: %s' % (value, e))
            sys.exit(1)
        except Exception:
            log.exception()
            sys.exit(1)


class Path(str):
    def __new__(cls, path):
        path = path.strip('"\'')
        if path:
            path = os.path.normpath(path)
        return str.__new__(cls, path)

    @property
    def normalized(self):
        return os.path.expanduser(self)


class Code(int):
    def __new__(cls, x):
        instance = super(Code, cls).__new__(cls, x)
        if not 100 <= instance <= 999:
            raise ValueError('Invalid HTTP response code: {}'.format(x))
        return instance


class MatchAnyCode(object):
    def __contains__(self, item):
        return True

    def __repr__(self):
        return '{0.__class__.__name__}()'.format(self)


class ResponseCodeList(object):
    def __init__(self, value):
        value = value.strip().lower()
        if value in ('all', 'any', 'yes', '*'):
            self._codes = MatchAnyCode()
        elif value in ('none', 'no'):
            self._codes = set()
        else:
            self._codes = {Code(code) for code in re.split(r'\s*,\s*', value)}

    def __contains__(self, item):
        return item in self._codes

    def __repr__(self):
        if isinstance(self._codes, MatchAnyCode):
            value = 'all'
        elif not self._codes:
            value = 'none'
        else:
            value = ','.join(sorted(self._codes))
        return '{0.__class__.__name__}({1!r})'.format(self, value)
