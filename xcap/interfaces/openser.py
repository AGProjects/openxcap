# Copyright (C) 2007 AG Projects.
#

"""The OpenSER Management Interface"""

from twisted.web import xmlrpc

from application.python.util import Singleton

class Result(str):
    """
    >>> r = Result('''200 OK
    ... ETag:: a.1218435715.10924.7.3
    ... Expires:: 3600''')

    >>> r.attrib['Expires']
    '3600'

    >>> r.attrib['ETag']
    'a.1218435715.10924.7.3'

    >>> r.first
    '200 OK'

    """

    def __init__(self, data):
        self.data = data
        lines = data.split('\n')
        self.first = lines[0]
        self.attrib = {}
        for (key, val) in (x.split(':: ') for x in lines[1:] if x.strip()):
            self.attrib[key] = val

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, self.data)


class ManagementInterface(object):
    __metaclass__ = Singleton

    def __init__(self, url):
        self.proxy = xmlrpc.Proxy(url + '/RPC2')

        # maps presentity uri --> etag
        self._etags = {}

    def notify_watchers(self, id, type=0):
        """Instruct OpenSER to NOTIFY all the watchers of this presentity.
           @type can be 0 to signal presence rules changes, or 1 for static PIDF changes."""
        d = self.proxy.callRemote('refreshWatchers', 'sip:' + id, 'presence', type)
        return d

    def publish_xcapdiff(self, user_uri, xcap_diff_body, supply_etag = True):
        """Issue PUBLISH with event=xcap-diff using"""
        user_uri = user_uri.uri
        if supply_etag:
            etag = self._etags.get(user_uri, '.')
        else:
            # discard saved etag if there's one
            self._etags.pop(user_uri, None)
            etag = '.'
        d = self.proxy.callRemote('pua_publish',
                                  user_uri,
                                  3600,
                                  'xcap-diff',
                                  'application/xcap-diff+xml',
                                  etag,
                                  '.',
                                  xcap_diff_body)

        # remember ETag returned by the function, so it can be used next time
        d.addCallback(lambda x: self._update_etag(x, user_uri, xcap_diff_body, etag))

        return d

    def _update_etag(self, x, user_uri, xcap_diff_body, used_etag):
        x = Result(x)
        if x.code == 418 and used_etag != '.':
            # we used some etag which was not recognised by pua - repeat
            # request with no etag at all
            return self.publish_xcapdiff(user_uri, xcap_diff_body, False)
        try:
            if 200 <= x.code <= 299:
                self._etags[user_uri] = x.attrib['ETag']
        except KeyError:
            pass
        return x

if __name__=='__main__':
    import doctest
    doctest.testmod()

    from twisted.internet import reactor
    MI = ManagementInterface('http://10.1.1.3:8080')
    print MI
    d = MI.publish_xcapdiff('sip:alice@localhost', 'XXXBODY')

    def callback1(message, x):
        print message, x

        def callback(message, x):
            print message, x
            reactor.callLater(0, reactor.stop)
            return x

        d = MI.publish_xcapdiff('sip:alice@localhost', 'XXXBODY2')
        d.addCallback(lambda x: callback('succeed', x))
        d.addErrback(lambda x: callback('failed', x))

        return x

    d.addCallback(lambda x: callback1('succeed', x))
    d.addErrback(lambda x: callback1('failed', x))

    reactor.run()
