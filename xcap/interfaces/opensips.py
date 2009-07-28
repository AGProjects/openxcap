# Copyright (C) 2007 AG Projects.
#

"""The OpenSIPS Management Interface"""

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
        try:
            code, self.message = self.first.split(' ', 1)
        except ValueError:
            self.code = None
            self.message = None
        else:
            try:
                self.code = int(code)
            except ValueError:
                self.code = None
                self.message = self.first
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
        """Instruct OpenSIPS to NOTIFY all the watchers of this presentity.
           @type can be 0 to signal presence rules changes, or 1 for static PIDF changes."""
        d = self.proxy.callRemote('refreshWatchers', 'sip:' + id, 'presence', type)
        return d

    def publish_xcapdiff(self, user_uri, xcap_diff_body, supply_etag = True):
        """Issue PUBLISH with event=xcap-diff using"""
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

        def update_etag(x):
            x = Result(x)
            try:
                if 200 <= x.code <= 299:
                    self._etags[user_uri] = x.attrib['ETag']
            except KeyError:
                pass
            return x

        def repeat_publish_if_wrong_etag(x):
            # a ValueError is raised for a negative response status code
            if isinstance(x.value, ValueError) and x.value.args and x.value[0] == '418' and etag != '.':
                # we used some etag which was not recognised by pua - repeat
                # request with no etag at all
                return self.publish_xcapdiff(user_uri, xcap_diff_body, False)
            return x

        # remember ETag returned by the function, so it can be used next time
        d.addCallbacks(update_etag, repeat_publish_if_wrong_etag)

        return d


if __name__=='__main__':
    import doctest
    doctest.testmod()

    from twisted.internet import reactor
    MI = ManagementInterface('http://127.0.0.1:8080')
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
