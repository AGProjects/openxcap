import sys
import unittest
import urllib2
import re
import types
from optparse import OptionParser


class HTTPRequest(urllib2.Request):
    """Hack urllib2.Request to support PUT and DELETE methods."""
    
    def __init__(self, url, method="GET", data=None, headers={},
                 origin_req_host=None, unverifiable=False):
        urllib2.Request.__init__(self,url,data,headers,origin_req_host,unverifiable)
        self.method = method
    
    def get_method(self):
        return self.method
    

class HTTPResponse(object):
    
    def __init__(self, url, code, msg, headers, body=None):
        self.url = url
        self.code = code
        self.msg = msg
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


class XCAPClient(object):

    xcap_root = 'http://127.0.0.1:8000'
    auth = 'basic'
    username = 'test@localhost'
    password = 'test'

    @classmethod
    def setupOptionParser(cls, parser):
        parser.add_option("--xcap-root", default=cls.xcap_root)
        parser.add_option("--auth", default=cls.auth)
        parser.add_option("--username", default=cls.username)
        parser.add_option("--password", default=cls.password)

    def initialize(self, options, _args = []):
        self.xcap_root = options.xcap_root
        self.auth = options.auth
        self.username = options.username
        self.password = options.password

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
            return HTTPResponse(url, r.code, r.msg, r.headers, r.read())
        except urllib2.HTTPError, e:
            headers = getattr(e, 'headers', {})
            return HTTPResponse(url, e.code, e.msg, headers, e.read())

    def get_resource(self, application, node=None, headers={}):
        username, domain = self.username.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.username)
        if node:
            uri += '~~' + node
        r = self._execute_request("GET", uri, username, domain, self.password, headers)
        self.status, self.headers, self.body = r.code, r.headers, r.body
        return r

    get=get_resource

    def put_resource(self, application, resource, node=None, headers={}):
        username, domain = self.username.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.username)
        if node:
            uri += '~~' + node
        r = self._execute_request("PUT", uri, username, domain, self.password, headers, resource)
        self.status, self.headers, self.body = r.code, r.headers, r.body
        return r

    put = put_resource

    def delete_resource(self, application, node=None, headers={}):
        username, domain = self.username.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.username)
        if node:
            uri += '~~' + node
        r = self._execute_request("DELETE", uri, username, domain, self.password, headers)
        self.status, self.headers, self.body = r.code, r.headers, r.body
        return r

    delete = delete_resource


class XCAPTest(unittest.TestCase, XCAPClient):

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

    def put_rejected(self, application, resource):
        self.delete_resource(application)
        self.assertStatus([200, 404])

        r = self.put_resource(application, resource)
        self.assertStatus(409)

        # the document shouldn't be there
        self.get_resource(application)
        self.assertStatus(404)

        self.status, self.headers, self.body = r.code, r.headers, r.body
        return r

    def getputdelete_successful(self, application, document, content_type):
        self.delete_resource(application)
        self.assertStatus([200, 404])

        self.get_resource(application)
        self.assertStatus(404)

        self.put_resource(application, document)
        self.assertStatus(201)

        self.get_resource(application)
        self.assertStatus(200)
        self.assertBody(document)
        self.assertHeader('Content-Type', content_type)

        self.put_resource(application, document)
        self.assertStatus(200)

        self.delete_resource(application)
        self.assertStatus(200)

        self.delete_resource(application)
        self.assertStatus(404)


class TestSuite(unittest.TestSuite):
    
    def initialize(self, options, args):
        for test in self._tests:
            test.options = options
            test.args = args
            if hasattr(test, 'initialize'):
                test.initialize(options, args)


class TestLoader(unittest.TestLoader):

    suiteClass = TestSuite

    def loadTestsFromModule_wparser(self, module, option_parser):
        """Return a suite of all tests cases contained in the given module"""
        tests = []
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, (type, types.ClassType)) and
                issubclass(obj, unittest.TestCase)):
                tests.append(self.loadTestsFromTestCase(obj))
                if hasattr(obj, 'setupOptionParser'):
                    obj.setupOptionParser(option_parser)
        return self.suiteClass(tests)


class TextTestRunner(unittest.TextTestRunner):

    def run_woptions(self, test, options, args):
        test.options = options
        test.args = args
        if hasattr(test, 'initialize'):
            test.initialize(options, args)
        return unittest.TextTestRunner.run(self, test)


def loadSuiteFromModule(module, option_parser):
    if isinstance(module, basestring):
        module = sys.modules[module]
    suite = TestLoader().loadTestsFromModule_wparser(module, option_parser)
    return suite


def runSuiteFromModule(module, settings=None):
    option_parser = OptionParser(conflict_handler='resolve')
    suite = loadSuiteFromModule(module, option_parser)
    options, args = option_parser.parse_args()
    TextTestRunner(verbosity=2).run_woptions(suite, options, args)

