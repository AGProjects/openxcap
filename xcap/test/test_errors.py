from common import *
import socket
from urlparse import urlparse

class ErrorsTest(XCAPTest):

    def communicate(self, data):
        s = socket.socket()
        x = urlparse(self.options.xcap_root)
        s.connect((x.hostname, x.port))
        s.send(data)
        return s.recv(1024*8)

    def test_gibberish(self):
        response = self.communicate('\r\r\r\n\r\n')
        assert '400 Bad Request' in response, `response`

    def test409(self):
        self.put('resource-lists', 'xxx', status=409)

    def test400(self):

        r = self.get('resource-lists', '/resource-lists/list[@name="friends"]/external[]/@anchor', status=400)

        def check(message, *uris):
            for uri in uris:
                r = self.client.con.request('GET', uri)
                self.assertEqual(r.code, 400)
                self.assertInBody(r, message)

        check('at least 2 segments', '', 'xxx')

        check("context is either 'users' or 'global'",
              'resource-lists/user/alice@example.com/index.xml')

        check('incomplete', 'resource-lists/users')

        check("must contain document's path",
              'resource-lists/users/alice@example.com',
              'resource-lists/users/alice@example.com/')

        check("to parse node",
              'resource-lists/users/alice@example.com/index.xml~~')

    def test405(self):
        r = self.client.con.request('POST', '')
        self.assertEqual(r.code, 405)

        r = self.client.con.request('XXX', '')
        self.assertEqual(r.code, 405) # but apache responds with 501

    # 404: already tested everywhere
    # 412: tested in test_etags.py

if __name__ == '__main__':
    runSuiteFromModule()
