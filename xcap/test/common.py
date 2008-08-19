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
        self.url = url
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

    @property
    def succeed(self):
        return 200 <= self.code <= 299
    
    def get_header(self, header):
        return self.headers.get(header)

    def __repr__(self):
        if self.body is None:
            bodylen = None
        else:
            bodylen = len(self.body)
        return "<%s.%s code=%d, datalen=%s>" % (self.__module__, self.__class__.__name__, self.code, bodylen)


class DebugOutput:

    file = sys.stderr

    def __init__(self, level):
        self.level = level

    def log_exception(self, req, ex):
        sys.stderr.write('%s %s\nRAISED %s %s\n' % (req.method, req.url, ex.__class__.__name__, ex))

    def log_trans(self, req, result):
        if self.level==1:
            self.log_method_url(req)
            self.log_result_code(result)
            self.log_etag(result)
        elif self.level==2:
            self.log_method_url(req)
            self.log_req_headers(req)
            self.log_result_code(result)
            self.log_result_headers(result)
        elif self.level>=3:
            self.log_method_url(req)
            self.log_req_headers(req)
            self.log_req_body(req)
            self.log_result_code(result)
            self.log_result_headers(result)
            self.log_result_body(result)

    def log_method_url(self, req):
        self.file.write('%s %s\n' % (req.method, req.url))

    def _log_headers(self, headers):
        for x in headers.items():
            self.file.write('%s: %s\n' % x)

    def log_etag(self, result):
        etag = result.headers.get('etag')
        if etag:
            self.file.write('etag: %s\n' % etag)

    def log_req_headers(self, req):
        self._log_headers(req.headers)

    def log_req_body(self, req):
        if req.body:
            self.file.write(req.body)
            if not req.body.endswith('\n'):
                self.file.write('\n')

    def log_result_code(self, result):
        self.file.write('%s %s\n' % (result.code, result.msg))

    def log_result_headers(self, result):
        self._log_headers(result.headers)

    def log_result_body(self, result):
        if result.body:
            self.file.write(result.body)
            if not result.body.endswith('\n'):
                self.file.write('\n')


class XCAPClient(object):

    xcap_root = 'http://127.0.0.1:8000'
    auth = 'basic'
    username = 'test@localhost'
    password = 'test'
    DebugOutput = DebugOutput
    debug_level = 0

    @classmethod
    def setupOptionParser(cls, parser):
        parser.set_defaults(debug_level=cls.debug_level)
        parser.add_option("--xcap-root", default=cls.xcap_root)
        parser.add_option("--auth", default=cls.auth)
        parser.add_option("--username", default=cls.username)
        parser.add_option("--password", default=cls.password)
        def increase_debug_level(_option, _opt_str, _value, parser):
            parser.values.debug_level = 1 + getattr(parser.values, 'debug_level', 0)
        parser.add_option("-d", action='callback', callback=increase_debug_level, nargs=0,
                          help="increase debug output. may be repeated.\n" + \
                          "-ddd means whole http bodies printed")

    def initialize(self, options, _args = []):
        self.xcap_root = options.xcap_root
        self.auth = options.auth
        self.username = options.username
        self.password = options.password
        self.debug = self.DebugOutput(getattr(options, 'debug_level', 0))

    def _execute_request(self, method, url, user, realm, password, headers={}, data=None):
        if self.auth == "basic":
            authhandler = urllib2.HTTPBasicAuthHandler()
        elif self.auth == "digest":
            authhandler = urllib2.HTTPDigestAuthHandler()
        authhandler.add_password(realm, url, user, password)
        opener = urllib2.build_opener(authhandler)
        urllib2.install_opener(opener)
        req = HTTPRequest(url, method=method, headers=headers, data=data)
        req.body = data
        try:
            r = urllib2.urlopen(req)
            result = HTTPResponse(url, r.code, r.msg, r.headers, r.read())
        except urllib2.HTTPError, e:
            headers = getattr(e, 'headers', {})
            result = HTTPResponse(url, e.code, e.msg, headers, e.read())
        except Exception, ex:
            self.debug.log_exception(req, ex)
            raise
        self.debug.log_trans(req, result)
        return result

    def get(self, application, node=None, headers={}):
        username, domain = self.username.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.username)
        if node:
            uri += '~~' + node
        return self._execute_request("GET", uri, username, domain, self.password, headers)

    def put(self, application, resource, node=None, headers={}):
        username, domain = self.username.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.username)
        if node:
            uri += '~~' + node
        return self._execute_request("PUT", uri, username, domain, self.password, headers, resource)

    def delete(self, application, node=None, headers={}):
        username, domain = self.username.split('@', 1)
        uri = "%s/%s/users/%s/index.xml" % (self.xcap_root, application, self.username)
        if node:
            uri += '~~' + node
        return self._execute_request("DELETE", uri, username, domain, self.password, headers)


class XCAPTest(unittest.TestCase):

    XCAPClient = XCAPClient

    @classmethod
    def setupOptionParser(cls, parser):
        cls.XCAPClient.setupOptionParser(parser)

    def initialize(self, options, args = []):
        self.options = options
        self.args = args

    def new_client(self):
        client = self.XCAPClient()
        client.initialize(self.options, self.args)
        return client

    def setUp(self):
        self.client = self.new_client()

    def assertStatus(self, r, status, msg=None):
        if status is None:
            return
        elif isinstance(status, int):
            if r.code != status:
                if msg is None:
                    msg = 'Status (%s) != %s' % (r.code, status)
                raise self.failureException(msg)
        else:
            ## status is a tuple or a list
            if r.code not in status:
                if msg is None:
                    msg = 'Status (%s) not in %s' % (r.code, str(status))
                raise self.failureException(msg)

    def assertHeader(self, r, key, value=None, msg=None):
        """Fail if (key, [value]) not in r.headers."""
        lowkey = key.lower()
        for k, v in r.headers.items():
            if k.lower() == lowkey:
                if value is None or str(value) == v:
                    return v
        if msg is None:
            if value is None:
                msg = '%s not in headers' % key
            else:
                msg = '%s:%s not in headers' % (key, value)
        raise self.failureException(msg)

    def assertNoHeader(self, r, key, msg=None):
        """Fail if key in r.headers."""
        lowkey = key.lower()
        matches = [k for k, v in r.headers if k.lower() == lowkey]
        if matches:
            if msg is None:
                msg = '%s in headers' % key
            raise self.failureException(msg)
    
    def assertBody(self, r, value, msg=None):
        """Fail if value != r.body."""
        if value.strip() != r.body.strip():
            if msg is None:
                msg = 'expected body:\n"%s"\n\nactual body:\n"%s"' % (value, r.body)
            raise self.failureException(msg)

    def assertInBody(self, r, value, msg=None):
        """Fail if value not in r.body."""
        if value not in r.body:
            if msg is None:
                msg = '%s not in body' % value
            raise self.failureException(msg)

    def assertNotInBody(self, r, value, msg=None):
        """Fail if value in r.body."""
        if value in r.body:
            if msg is None:
                msg = '%s found in body' % value
            raise self.failureException(msg)
    
    def assertMatchesBody(self, r, pattern, msg=None, flags=0):
        """Fail if value (a regex pattern) is not in r.body."""
        if re.search(pattern, r.body, flags) is None:
            if msg is None:
                msg = 'No match for %s in body' % pattern
            raise self.failureException(msg)

    def get(self, application, node=None, headers={}, status=200, client=None):
        client = client or self.client
        r = client.get(application, node, headers)
        self.assertStatus(r, status)
        return r

    def put(self, application, resource, node=None, headers={},
            status=[200,201], content_type_in_GET=None, client=None):
        client = client or self.client
        r_put = client.put(application, resource, node, headers)
        self.assertStatus(r_put, status)

        # if PUTting succeed, check that document is there and equals to resource
        if r_put.succeed:
            r_get = client.get(application, node)
            self.assertStatus(r_get, 200,
                              'although PUT succeed, following GET on the same URI did not: %s %s' % \
                              (r_get.code, r_get.msg))
            self.assertEqual(resource, r_get.body) # is body put equals to body got?
            if content_type_in_GET is not None:
                self.assertHeader(r_get, 'content-type', content_type_in_GET)

        return r_put

    def delete(self, application, node=None, headers={}, status=200, client=None):
        client = client or self.client
        r = client.delete(application, node, headers)
        self.assertStatus(r, status)

        # if deleting succeed, GET should return 404
        if r.succeed or r.code == 404:
            r_get = client.get(application, node, headers)
            self.assertStatus(r_get, 404,
                              'although DELETE succeed, following GET on the same URI did not return 404: %s %s' % \
                              (r_get.code, r_get.msg))

        return r

    def put_rejected(self, application, resource, status=409, client=None):
        """DELETE the document, then PUT it and expect 409 error. Return PUT result.
        If PUT has indeed failed, also check that GET returns 404
        """
        self.delete(application, status=[200,404], client=client)
        put_result = self.put(application, resource, status=status, client=client)
        self.get(application, status=404, client=client)
        return put_result

    def getputdelete(self, application, document, content_type, client=None):
        self.delete(application, status=[200,404], client=client)
        self.get(application, status=404, client=client)
        self.put(application, document, status=201, content_type_in_GET=content_type, client=client)
        self.put(application, document, status=200, content_type_in_GET=content_type, client=client)
        self.put(application, document, status=200, content_type_in_GET=content_type, client=client)
        self.delete(application, status=200, client=client)
        self.delete(application, status=404, client=client)


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


def runSuiteFromModule(module='__main__'):
    option_parser = OptionParser(conflict_handler='resolve')
    suite = loadSuiteFromModule(module, option_parser)
    options, args = option_parser.parse_args()
    TextTestRunner(verbosity=2).run_woptions(suite, options, args)

