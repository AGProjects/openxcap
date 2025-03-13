
"""Track changes of the documents and notify subscribers

Create a Notifier object:

  >>> n = Notifier(xcap_root, publish_xcapdiff_func)

When a change occurs, call on_change

  >>> n.on_change(xcap_uri_updated, old_etag, new_etag)

(old_etag being None means the document was just created, new_etag being
None means the document was deleted)

Notifier will call publish_xcapdiff_func with 2 args: user's uri and xcap-diff document.
Number of calls is limited to no more than 1 call per MIN_WAIT seconds for
a given user uri.

"""
import asyncio
from functools import wraps
from time import time
from typing import Any, Dict, List, Optional, Union

from xcap.configuration.datatypes import XCAPRootURI
from xcap.types import PublishFunction, PublishWrapper
from xcap.uri import XCAPUri


def xml_xcapdiff(xcap_root: XCAPRootURI, content: str) -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<xcap-diff xmlns="urn:ietf:params:xml:ns:xcap-diff" xcap-root="%s">
%s
</xcap-diff>
""" % (xcap_root, content)


def xml_document(sel: XCAPUri, old_etag: str, new_etag: Union[str, None]) -> str:
    if old_etag:
        old_etag = (' previous-etag="%s"' % old_etag)
    else:
        old_etag = ''
    if new_etag:
        new_etag = (' new-etag="%s"' % new_etag)
    else:
        new_etag = ''
    return '<document%s sel="%s"%s/>' % (new_etag, sel, old_etag)


class UserChanges(object):
    MIN_WAIT = 30

    def __init__(self, publish_xcapdiff: PublishFunction):
        self.changes: Dict[XCAPUri, List[Any]] = {}
        self.rate_limit = RateLimit(self.MIN_WAIT)
        self.publish_xcapdiff = publish_xcapdiff

    async def add_change(self, uri: XCAPUri, old_etag: str, etag: Union[str, None], xcap_root: XCAPRootURI) -> None:
        self.changes.setdefault(uri, [old_etag, etag])[1] = etag
        await self.rate_limit.callAtLimitedRate(self.publish, uri.user.uri, xcap_root)

    async def publish(self, user_uri: str, xcap_root: XCAPRootURI) -> None:
        if self.changes:
            self.publish_xcapdiff(user_uri, self.unload_changes(xcap_root))

    def unload_changes(self, xcap_root: XCAPRootURI) -> str:
        docs = []
        for uri, (old_etag, etag) in self.changes.items():
            docs.append(xml_document(uri, old_etag, etag))
        result = xml_xcapdiff(xcap_root, '\n'.join(docs))
        self.changes.clear()
        return result

    def __bool__(self) -> bool:
        return bool(self.changes)


class Notifier(object):
    def __init__(self, xcap_root: XCAPRootURI, publish_xcapdiff_func: PublishFunction) -> None:
        self.publish_xcapdiff = publish_xcapdiff_func
        self.xcap_root = xcap_root

        # maps user_uri to UserChanges
        self.users_changes: Dict[str, UserChanges] = {}

    async def on_change(self, uri: XCAPUri, old_etag: str, new_etag: Optional[str]) -> None:
        changes = self.users_changes.setdefault(str(uri.user), UserChanges(self.publish_xcapdiff))
        await changes.add_change(uri, old_etag, new_etag, self.xcap_root)


class RateLimit:
    def __init__(self, min_wait: int):
        self.min_wait = min_wait
        self.last_call = 0.0
        self.delayed_call: Optional[asyncio.Task] = None

    async def callAtLimitedRate(self, f: PublishWrapper, *args, **kwargs) -> None:
        current = time()
        delta = current - self.last_call
        if self.delayed_call is None or self.delayed_call.done():
            await self._schedule(f, args, kwargs, delta)

    async def _schedule(self, f: PublishWrapper, args, kwargs, delta: float) -> None:
        if delta >= self.min_wait:
            self.last_call = time()
            await f(*args, **kwargs)
        else:
            self.delayed_call = asyncio.create_task(self._delayed_call(f, args, kwargs, delta))

    async def _delayed_call(self, f: PublishWrapper, args, kwargs, delta: float) -> None:
        await asyncio.sleep(self.min_wait - delta)  # Wait for the remaining time
        self.last_call = time()  # Update the last call time
        await f(*args, **kwargs)  # Call the function
        self.delayed_call = None  # Clear the delayed call once it's executed


class RateLimitedFun(RateLimit):
    def __init__(self, min_wait: int, function):
        RateLimit.__init__(self, min_wait)
        self.function = function

    def __call__(self, *args, **kwargs):
        return self.callAtLimitedRate(self.function, *args, **kwargs)


def limit_rate(min_wait: int):
    """Decorator for limiting rate of the function.
    The resulting value of the new function will be None regardless of
    what the wrapped function returned.

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

    def decorate(f: PublishFunction):
        @wraps(f)
        async def wrapped(*args, **kwargs):
            await rate.callAtLimitedRate(f, *args, **kwargs)
        return wrapped
    return decorate


if __name__ == '__main__':
    import doctest
    doctest.testmod()
