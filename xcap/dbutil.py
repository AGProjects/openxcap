"""Database utilities"""

import os
import md5
import time
import random
import urllib

from twisted.enterprise import adbapi
from twisted.python import reflect

db_modules = {"mysql": "MySQLdb"}

def make_random_etag(uri):
    return md5.new("%s%s%s" % (uri, time.time(), random.random())).hexdigest()

def make_etag(uri, document):
    return md5.new("%s%s" % (uri, document)).hexdigest()

def parseURI(uri):
    schema, rest = uri.split(':', 1)
    assert rest.startswith('//'), "DB URIs must start with scheme:// -- you did not include a / (in %r)" % rest
    rest = rest[2:]
    if rest.find('/') != -1:
        host, rest = rest.split('/', 1)
    else:
        raise ValueError("You MUST specify a database in the DB URI.")

    if host and host.find('@') != -1:
        user, host = host.split('@', 1)
        if user.find(':') != -1:
            user, password = user.split(':', 1)
        else:
            password = None
        if not user:
            raise ValueError("You MUST specify a user in the DB URI.")
    else:
        raise ValueError("You MUST specify a host in the DB URI.")

    if host and host.find(':') != -1:
        host, port = host.split(':')
        try:
            port = int(port)
        except ValueError:
            raise ValueError, "port must be integer, got '%s' instead" % port
        if not (1 <= port <= 65535):
            raise ValueError, "port must be integer in the range 1-65535, got '%d' instead" % port
    else:
        port = None
    db = rest
    return schema, user, password, host, port, db

def connectionForURI(uri):
    """Return a Twisted adbapi connection pool for a given database URI."""
    schema, user, password, host, port, db = parseURI(uri)
    try:
        module = db_modules[schema]
    except KeyError:
        raise ValueError("Database scheme '%s' is not supported." % schema)

    # Reconnecting is safe since we don't use transactions.
    # the following code prefers MySQLdb native reconnect if it's available,
    # falling back to twisted's cp_reconnect.
    # mysql's reconnect is preferred because it's better tested than twisted's
    # MySQLdb reconnect just works with version 1.2.2 it has been removed after
    kwargs = {}
    if module == 'MySQLdb':
        MySQLdb = reflect.namedModule(module)
        if MySQLdb.version_info[:3] == (1, 2, 2):
            kwargs.setdefault('reconnect', 1)
        kwargs.setdefault('host', host or 'localhost')
        kwargs.setdefault('user', user or '')
        kwargs.setdefault('passwd', password or '')
        kwargs.setdefault('db', db)
        args = ()

    if 'reconnect' not in kwargs:
        # note that versions other than 1.2.2 of MySQLdb don't provide reconnect parameter.
        # hopefully, if underlying reconnect was enabled, twisted will never see
        # a disconnect and its reconnection code won't interfere.
        kwargs.setdefault('cp_reconnect', 1)

    kwargs.setdefault('cp_noisy', False)

    pool = adbapi.ConnectionPool(module, *args, **kwargs)
    pool.schema = schema
    return pool

def repeat_on_error(N, errorinfo, func, *args, **kwargs):
    d = func(*args, **kwargs)
    counter = [N]
    def try_again(error):
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

