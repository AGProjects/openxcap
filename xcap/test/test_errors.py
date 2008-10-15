from common import *
import socket
from urlparse import urlparse

class ErrorsTest(XCAPTest):

    def communicate(self, data):
        s = socket.socket()
        x = urlparse(self.options.xcap_root)
        if x.port is None:
            port = {'http': 80, 'https': 443}.get(x.scheme)
        s.connect((x.hostname, x.port or port))
        if x.scheme == 'https':
            s = socket.ssl(s)
            s.write(data)
            return s.read(1024*8)
        s.send(data)
        return s.recv(1024*8)

    def test_gibberish(self):
        response = self.communicate('\r\r\r\n\r\n')
        assert '400 Bad Request' in response, `response`

    def test409(self):
        self.put('resource-lists', 'xxx', status=409)

    def check(self, code, message, *uris):
        for uri in uris:
            r = self.client.con.request('GET', uri)
            self.assertEqual(r.code, code)
            self.assertInBody(r, message)

    def test400(self):

        self.get('resource-lists', '/resource-lists/list[@name="friends"]/external[]/@anchor', status=400)

        self.check(400, "to parse node",
                   'resource-lists/users/alice@example.com/index.xml~~')

    def test404(self):

        self.check(404, 'XCAP Root', '')

        self.check(404, 'context', 'xxx')

        self.check(404, "context",
                   'resource-lists/user/alice@example.com/index.xml')

        self.check(404, 'user id', 'resource-lists/users')

        self.check(404, "not contain ",
                   'resource-lists/users/alice@example.com',
                   'resource-lists/users/alice@example.com/')

        # XXX test for multiple matches

    def test405(self):
        r = self.client.con.request('POST', '')
        self.assertEqual(r.code, 405)

        r = self.client.con.request('XXX', '')
        self.assertEqual(r.code, 405) # but apache responds with 501

    # 412: tested in test_etags.py

if __name__ == '__main__':
    runSuiteFromModule()
