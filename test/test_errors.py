#!/usr/bin/env python3

# Copyright (C) 2007-2025 AG-Projects.
#
import ssl
from urllib.parse import urlparse

import common as c


class ErrorsTest(c.XCAPTest):

    def communicate(self, data):
        s = c.socket.socket()
        x = urlparse(self.options.xcap_root)
        if x.port is None:
            port = {'http': 80, 'https': 443}.get(x.scheme)
        s.connect((x.hostname, x.port or port))
        if x.scheme == 'https':
            context = ssl.create_default_context()
            context.check_hostname = False  # Disable hostname verification
            context.verify_mode = ssl.CERT_NONE  # Disable certificate verification

            s = context.wrap_socket(s, server_hostname=x.hostname)
        s.send(data)
        return s.recv(1024*8)

    def test_gibberish(self):
        response = self.communicate(b'\r\r\r\n\r\n1')
        assert '400 Bad Request' in response.decode(), repr(response)
   
    def test409(self):
        self.put('resource-lists', 'xxx', status=409)

    def check(self, code, message, *uris):
        for uri in uris:
            r = self.client.client.request('GET', uri)
            self.assertEqual(r.status, code)
            self.assertInBody(r, message)

    def test400_1(self):

        self.get('resource-lists', '/resource-lists/list[@name="friends"]/external[]/@anchor', status=400)

    def test400_2(self):

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
        r = self.client.client.request('POST', '')
        self.assertEqual(r.status, 405)

        r = self.client.client.request('XXX', '')
        self.assertIn(r.status, [400, 405]) # but apache responds with 501

    # 412: tested in test_etags.py

if __name__ == '__main__':
    c.runSuiteFromModule()
