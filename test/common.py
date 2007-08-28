# Copyright (C) 2007 AG Projects.
#


import unittest
import urllib2
import re


class HTTPRequest(urllib2.Request):
    """Hack urllib2.Request to support PUT and DELETE methods."""
    
    def __init__(self, url, method="GET", data=None, headers={},
                 origin_req_host=None, unverifiable=False):
        urllib2.Request.__init__(self,url,data,headers,origin_req_host,unverifiable)
        self.method = method
    
    def get_method(self):
        return self.method
    

class HTTPResponse(object):
    
    def __init__(self, code, headers, body=None):
        self.code = code
        self.headers = headers
        self.body = body
    
    def get_header(self, header):
        return self.headers.get(header)

    def __repr__(self):
        if self.body is None:
            bodylen = None
        else:
            bodylen = len(self.body)
        return "<%s.%s code=%d, datalen=%s>" % (self.__module__, self.__class__.__name__, self.code, bodylen)


class XCAPTest(unittest.TestCase):
    xcap_root = 'http://10.0.0.1:433/xcap-root'
    auth = 'basic'
    account = 'test@example.com'
    password = 'test'

    def _execute_request(self, method, url, user, realm, password, headers={}, data=None):
        if self.auth == "basic":
            authhandler = urllib2.HTTPBasicAuthHandler()
        elif self.auth == "digest":
            authhandler = urllib2.HTTPDigestAuthHandler()
        authhandler.add_password(realm, url, user, password)
        opener = urllib2.build_opener(authhandler)
        urllib2.install_opener(opener)
        req = HTTPRequest(url, method=method, headers=headers, data=data)
        try:
            r = urllib2.urlopen(req)
            return HTTPResponse(r.code, r.headers, r.read())
        except urllib2.HTTPError, e:
            headers = getattr(e, 'headers', {})
            return HTTPResponse(e.code, headers)

    def get_resource(self, application, node=None, headers={}):
        username, domain = self.account.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.account)
        if node:
            uri += '~~' + node
        r = self._execute_request("GET", uri, username, domain, self.password, headers)
        self.status, self.headers, self.body = r.code, r.headers, r.body

    def put_resource(self, application, resource, node=None, headers={}):
        username, domain = self.account.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.account)
        if node:
            uri += '~~' + node
        r = self._execute_request("PUT", uri, username, domain, self.password, headers, resource)
        self.status, self.headers, self.body = r.code, r.headers, r.body

    def delete_resource(self, application, node=None, headers={}):
        username, domain = self.account.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.account)
        if node:
            uri += '~~' + node
        r = self._execute_request("DELETE", uri, username, domain, self.password, headers)
        self.status, self.headers, self.body = r.code, r.headers, r.body

    def assertStatus(self, status, msg=None):
        if isinstance(status, int):
            if self.status != status:
                if msg is None:
                    msg = 'Status (%s) != %s' % (self.status, status)
                raise self.failureException(msg)
        else:
            ## status is a tuple or a list
            if self.status not in status:
                if msg is None:
                    msg = 'Status (%s) not in %s' % (self.status, str(status))
                raise self.failureException(msg)

    def assertHeader(self, key, value=None, msg=None):
        """Fail if (key, [value]) not in self.headers."""
        lowkey = key.lower()
        for k, v in self.headers.items():
            if k.lower() == lowkey:
                if value is None or str(value) == v:
                    return v
        if msg is None:
            if value is None:
                msg = '%s not in headers' % key
            else:
                msg = '%s:%s not in headers' % (key, value)
        raise self.failureException(msg)

    def assertNoHeader(self, key, msg=None):
        """Fail if key in self.headers."""
        lowkey = key.lower()
        matches = [k for k, v in self.headers if k.lower() == lowkey]
        if matches:
            if msg is None:
                msg = '%s in headers' % key
            raise self.failureException(msg)
    
    def assertBody(self, value, msg=None):
        """Fail if value != self.body."""
        if value != self.body:
            if msg is None:
                msg = 'expected body:\n"%s"\n\nactual body:\n"%s"' % (value, self.body)
            raise self.failureException(msg)

    def assertInBody(self, value, msg=None):
        """Fail if value not in self.body."""
        if value not in self.body:
            if msg is None:
                msg = '%s not in body' % value
            raise self.failureException(msg)

    def assertNotInBody(self, value, msg=None):
        """Fail if value in self.body."""
        if value in self.body:
            if msg is None:
                msg = '%s found in body' % value
            raise self.failureException(msg)
    
    def assertMatchesBody(self, pattern, msg=None, flags=0):
        """Fail if value (a regex pattern) is not in self.body."""
        if re.search(pattern, self.body, flags) is None:
            if msg is None:
                msg = 'No match for %s in body' % pattern
            raise self.failureException(msg)
