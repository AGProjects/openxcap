"""Track changes of the documents and notify subscribers

Create a Notifier object:

  >>> n = Notifier(publish_xcapdiff)

When a change occurs, call on_change

  >>> n.on_change(xcap_uri_updated, old_etag, new_etag)

(old_etag being None means the document was just created, new_etag being
None means the document was deleted)

Notifier will call publish_xcapdiff with 2 args: user's uri and xcap-diff document.
Number of calls is limited to no more than 1 call per MIN_WAIT seconds for
a given user uri.

"""

from time import time
from functools import wraps
from twisted.internet import defer
from twisted.internet import reactor

def xml_xcapdiff(xcap_root, content):
    return """<?xml version="1.0" encoding="UTF-8"?>
<xcap-diff xmlns="urn:ietf:params:xml:ns:xcap-diff" xcap-root="%s">
%s
</xcap-diff>
""" % (xcap_root, content)

def xml_document(sel, old_etag, new_etag):
    if old_etag:
        old_etag = ( ' previous-etag="%s"' % old_etag )
    else:
	old_etag = ''
    if new_etag:
        new_etag = ( ' new-etag="%s"' % new_etag )
    else:
	new_etag = ''
    return '<document%s sel="%s"%s/>' % (new_etag, sel, old_etag)


class UserChanges:

    MIN_WAIT = 5

    def __init__(self, publish_xcapdiff):
        self.changes = {}
        self.rate_limit = RateLimit(self.MIN_WAIT)
        self.publish_xcapdiff = publish_xcapdiff

    def add_change(self, uri, old_etag, etag, xcap_root):
        self.changes.setdefault(uri, [old_etag, etag])[1] = etag
        self.rate_limit.callAtLimitedRate(self.publish, uri.user.uri, xcap_root)

    def publish(self, user_uri, xcap_root):
        if self.changes:
            self.publish_xcapdiff(user_uri, self.unload_changes(xcap_root))
    
    def unload_changes(self, xcap_root):
        docs = []
        for uri, (old_etag, etag) in self.changes.iteritems():
            docs.append(xml_document(uri, old_etag, etag))
        result = xml_xcapdiff(xcap_root, '\n'.join(docs))
        self.changes.clear()
        return result

    def __nonzero__(self):
        return self.changes.__nonzero__()


class Notifier:

    def __init__(self, xcap_root, publish_xcapdiff):
        self.publish_xcapdiff = publish_xcapdiff
        self.xcap_root = xcap_root

        # maps user_uri to UserChanges
        self.users_changes = {}

    def on_change(self, uri, old_etag, new_etag):
        changes = self.users_changes.setdefault(uri.user, UserChanges(self.publish_xcapdiff))
        changes.add_change(uri, old_etag, new_etag, self.xcap_root)


class RateLimit(object):

    def __init__(self, min_wait):
        # minimum number of seconds between calls
        self.min_wait = min_wait

        # time() of the last call
        self.last_call = 0

        # DelayedCall object of scheduled call
        self.delayed_call = None

    def callAtLimitedRate(self, f, *args, **kwargs):
        """Call f(*args, **kw) if it wasn't called in the last self.min_wait seconds.
        If it was, schedule it for later. Don't do anything if it's already scheduled.

        >>> rate = RateLimit(1)

        >>> def f(a, start = time()):
        ...     print "%d %s" % (time()-start, a)
        ...     return 'return value is lost!'

        >>> rate.callAtLimitedRate(f, 'a')
        0 a
        >>> rate.callAtLimitedRate(f, 'b') # scheduled for 1 second later
        >>> rate.callAtLimitedRate(f, 'c') # ignored as there's already call in progress
        >>> _ = reactor.callLater(1.5, rate.callAtLimitedRate, f, 'd')
        >>> _ = reactor.callLater(2.1, reactor_stop)
        >>> reactor_run()
        1 b
        2 d
        """
        current = time()
        delta = current - self.last_call
        if not self.delayed_call or \
               self.delayed_call.called or \
               self.delayed_call.cancelled:
            @wraps(f)
            def wrapped_f():
                try:
                    return f(*args, **kwargs)
                finally:
                    self.last_call = time()
            self.delayed_call = callMaybeLater(self.min_wait - delta, wrapped_f)


class RateLimitedFun(RateLimit):

    def __init__(self, min_wait, function):
        RateLimit.__init__(self, min_wait)
        self.function = function

    def __call__(self, *args, **kwargs):
        return self.callAtLimitedRate(self.function, *args, **kwargs)


def limit_rate(min_wait):
    """resulting value for the function will become None

    >>> @limit_rate(1)
    ... def f(a, start = time()):
    ...     print "%d %s" % (time()-start, a)
    ...     return 'return value is lost!'
    >>> f('a')
    0 a
    >>> f('b') # scheduled for 1 second later
    >>> f('c') # ignored as there's already call in progress
    >>> _ = reactor.callLater(1.5, f, 'd')
    >>> _ = reactor.callLater(2.1, reactor_stop)
    >>> reactor_run()
    1 b
    2 d
    """

    rate = RateLimit(min_wait)
    
    def decorate(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            rate.callAtLimitedRate(f, *args, **kwargs)
        return wrapped
    return decorate


def callMaybeLater(seconds, f, *args, **kw):
    "execute f and return None if seconds is zero, callLater otherwise"
    if seconds <= 0:
        f(*args, **kw)
    else:
        return reactor.callLater(seconds, f, *args, **kw)

if __name__=='__main__':
    def reactor_run(first_time = [True]):
        if first_time[0]:
            reactor.run()
            first_time[0] = False
        else:
            reactor.running = True
            reactor.mainLoop()

    def reactor_stop():
        reactor.running = False
    
    import doctest
    doctest.testmod()

