"""Database utilities"""

import os
import md5
import time

from twisted.enterprise import adbapi
from twisted.python import reflect

db_modules = {"mysql": "MySQLdb",
              "sqlite": "sqlite3"}

def generate_etag(uri, document):
    """Generate an etag for the given XCAP URI and document.

    @param uri: an XCAP URI that contains the XCAP user and the document selector

    @param document: an XCAP document
    """
    if hasattr(uri, 'xcap_root'):
        return md5.new(uri.xcap_root + str(uri.doc_selector) + str(time.time())).hexdigest()
    else:
        return md5.new(uri + str(time.time())).hexdigest()


def parseURI(uri):
    """
    >>> parseURI('mysql://username:123@localhost/openser')
    ('mysql', 'username', '123', 'localhost', None, '/openser', {})
    >>> parseURI('sqlite:/:memory:')
    ('sqlite', None, None, None, None, ':memory:', {})
    >>> parseURI('sqlite:///full/path/to/database')
    ('sqlite', None, None, None, None, '/full/path/to/database', {})
    >>> parseURI('sqlite:/C|/full/path/to/database')
    ('sqlite', None, None, None, None, '/C|/full/path/to/database', {})
    """
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
    if path == '/:memory:':
        path = path[1:]
    return schema, user, password, host, port, path, args

def connectionForURI(uri):
    """Return a Twisted adbapi connection pool for a given database URI."""
    schema, user, password, host, port, path, args = parseURI(uri)
    try:
        module = db_modules[schema]
    except Exception:
        raise AssertionError("Database scheme '%s' is not supported." % schema)

    # reconnecting is safe since we don't use transactions.
    # the following code prefers MySQLdb native reconnect if it's available,
    # falling back to twisted's cp_reconnect.
    # mysql's reconnect is preferred because it's better tested than twisted's
    kwargs = {}
    if module == 'MySQLdb':
        MySQLdb = reflect.namedModule(module)
        if MySQLdb.version_info[:3] >= (1, 2, 2):
            kwargs.setdefault('reconnect', 1)
        kwargs.setdefault('host', host or 'localhost')
        kwargs.setdefault('user', user or '')
        kwargs.setdefault('passwd', password or '')
        path = path.lstrip('/')
        kwargs.setdefault('db', path)
        args = ()
    elif module == 'sqlite3':
        if path == ':memory:':
            # otherwise a database per connection is created
            kwargs['cp_min'] = kwargs['cp_max'] = 1
        args = (path, )

    if 'reconnect' not in kwargs:
        # note that some versions of MySQLdb don't provide reconnect parameter,
        # but set it to 1.
        # hopefully, if underlying reconnect was enabled, twisted will never see
        # a disconnect and its reconnection code won't interfere.
        kwargs.setdefault('cp_reconnect', 1)

    kwargs.setdefault('cp_noisy', False)

    pool = adbapi.ConnectionPool(module, *args, **kwargs)
    pool.schema = schema
    return pool

def repeat_on_error(N, errorinfo, func, *args, **kwargs):
    #print 'repeat_on_error', N, func.__name__
    d = func(*args, **kwargs)
    counter = [N]
    def try_again(error):
        #print 'try_again!', func.__name__, counter[0], `error`
        if isinstance(error.value, errorinfo) and counter[0]>0:
            counter[0] -= 1
            d = func(*args, **kwargs)
            d.addErrback(try_again)
            return d
        return error
    d.addErrback(try_again)
    return d

if __name__=='__main__':
    from twisted.internet import defer

    def s():
        print 's()'
        return defer.succeed(True)
    def f():
        print 'f()'
        return defer.fail(ZeroDivisionError())

    def getcb(msg):
        def callback(x):
            print '%s callback: %r' % (msg, x)
        def errback(x):
            print '%s errback: %r' % (msg, x)
        return callback, errback

    # calls s()'s callback
    d = repeat_on_error(1, Exception, s)
    d.addCallbacks(*getcb('s'))

    # calls f() for 4 times (1+3), then gives up and calls last f()'s errback
    d = repeat_on_error(3, Exception, f)
    d.addCallbacks(*getcb('f'))

    x = Exception()
    x.lst = [f, f, s]

    def bad_func():
        f, x.lst = x.lst[0], x.lst[1:]
        return f()

    d = repeat_on_error(1, Exception, bad_func)
    d.addCallbacks(*getcb('bad_func'))
    
