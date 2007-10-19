"""Database utilities"""

import os

from twisted.enterprise import adbapi, util as dbutil

db_modules = {"mysql": "MySQLdb"}

def parseURI(uri):
    schema, rest = uri.split(':', 1)
    assert rest.startswith('/'), "URIs must start with scheme:/ -- you did not include a / (in %r)" % rest
    if rest.startswith('/') and not rest.startswith('//'):
        host = None
        rest = rest[1:]
    elif rest.startswith('///'):
        host = None
        rest = rest[3:]
    else:
        rest = rest[2:]
        if rest.find('/') == -1:
            host = rest
            rest = ''
        else:
            host, rest = rest.split('/', 1)
    if host and host.find('@') != -1:
        user = host[:host.rfind('@')] # Python 2.3 doesn't have .rsplit()
        host = host[host.rfind('@')+1:] # !!!
        if user.find(':') != -1:
            user, password = user.split(':', 1)
        else:
            password = None
    else:
        user = password = None
    if host and host.find(':') != -1:
        _host, port = host.split(':')
        try:
            port = int(port)
        except ValueError:
            raise ValueError, "port must be integer, got '%s' instead" % port
        if not (1 <= port <= 65535):
            raise ValueError, "port must be integer in the range 1-65535, got '%d' instead" % port
        host = _host
    else:
        port = None
    path = '/' + rest
    if os.name == 'nt':
        if (len(rest) > 1) and (rest[1] == '|'):
            path = "%s:%s" % (rest[0], rest[2:])
    args = {}
    if path.find('?') != -1:
        path, arglist = path.split('?', 1)
        arglist = arglist.split('&')
        for single in arglist:
            argname, argvalue = single.split('=', 1)
            argvalue = urllib.unquote(argvalue)
            args[argname] = argvalue
    return schema, user, password, host, port, path, args

def connectionForURI(uri):
    """Return a Twisted adbapi connection pool for a given database URI."""
    schema, user, password, host, port, path, args = parseURI(uri)
    try:
        module = db_modules[schema]
    except:
        raise AssertionError("Database scheme '%s' is not supported." % schema)
    return adbapi.ConnectionPool(module, db=path.strip('/'), user=user or '',
                                 passwd=password or '', host=host or 'localhost', cp_noisy=False)
