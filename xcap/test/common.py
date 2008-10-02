import sys
import unittest
import re
import types
from optparse import OptionParser
from copy import copy


xcaplib_min_version = (1, 0, 2)

sys.path.append('../../../python-xcaplib')
import xcaplib
try:
    xcaplib.version_info
except AttributeError:
    raise ImportError('Need python-xcaplib of version at least %s.%s.%s' % xcaplib_min_version)

if xcaplib.version_info[:3]<xcaplib_min_version:
    raise ImportError('Need python-xcaplib of version at least %s.%s.%s, you have %s.%s.%s' % \
                      (xcaplib_min_version + xcaplib.version_info[:3]))

from xcaplib.client import Resource, HTTPError
from xcaplib.xcapclient import setup_parser_client, make_xcapclient, read_xcapclient_cfg
del sys.path[-1]


apps = ['pres-rules',
        'org.openmobilealliance.pres-rules',
        'resource-lists',
        'pidf-manipulation',
        'watchers',
        'rls-services',
        'test-app',
        'xcap-caps']


def format_httperror(e):
    try:
        headers = e.hdrs
    except AttributeError:
        # HTTPError has hdrs method, but addinfourl has headers
        headers = e.headers
    return "%s %s\n%s\n%s" % (e.code, e.msg, headers, e.body)

# the tests expect to receive reply object with 'body' attribute
class HTTPConnectionWrapper(xcaplib.client.HTTPConnectionWrapper):
    debug = False

    def __init__(self, *args):
        return xcaplib.client.HTTPConnectionWrapper.__init__(self, *args)

    def request(self, *args, **kwargs):
        r = None
        try:
            r = xcaplib.client.HTTPConnectionWrapper.request(self, *args, **kwargs)
            r.body = r.read()
        except HTTPError, e:
            r = e
            r.body = r.read()
        except Exception, ex:
            print args, kwargs
            raise
        finally:
            if self.debug and r:
                print r.req.format()
                print
                print format_httperror(r)
                print

        return r

    def get(self, path, headers=None, etag=None):
        return self.request('GET', path, headers, None, etag)

xcaplib.client.XCAPClient.HTTPConnectionWrapper = HTTPConnectionWrapper

def succeed(r):
    return 200 <= r.code <= 299

class XCAPTest(unittest.TestCase):

    # if true, each PUT or DELETE will be followed by GET to ensure that it has indeed succeeded
    invariant_check = True

    @classmethod
    def setupOptionParser(cls, parser):
        setup_parser_client(parser) # QQQ should it be there? it executes the same code multiple times

    def initialize(self, options, args = []):
        if not hasattr(self, '_options'):
            self._options = copy(options)
        if not hasattr(self, '_args'):
            self._args = copy(args)

    def new_client(self):
        return make_xcapclient(self.options)

    def update_client_options(self):
        self.client = self.new_client()

    def setUp(self):
        self.options = self._options
        self.args = self._args
        self.update_client_options()

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

    def assertETag(self, r):
        v = self.assertHeader(r, 'ETag')
        return xcaplib.client.parse_etag_value(v)

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
        if value != r.body:
            if msg is None:
                msg = 'expected body:\n"%s"\n\nactual body:\n"%s"' % (value, r.body)
            raise self.failureException(msg)

    def assertInBody(self, r, value, msg=None):
        """Fail if value not in r.body."""
        if value not in r.body:
            if msg is None:
                msg = '%r not in body\nbody: %r' % (value, r.body)
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

    def assertDocument(self, application, body, client=None):
        r = self.get(application, client=client)
        self.assertBody(r, body)

    def get(self, application, node=None, status=200, **kwargs):
        client = kwargs.pop('client', None) or self.client
        r = client.get(application, node, **kwargs)
        self.assertStatus(r, status)
        if 200<=status<=299:
            self.assertHeader(r, 'ETag')
        return r

    def get_global(self, *args, **kwargs):
        kwargs['globaltree'] = True
        return self.get(*args, **kwargs)

    def put(self, application, resource, node=None,
            status=[200,201], content_type_in_GET=None, client=None, **kwargs):
        client = client or self.client
        r_put = client.put(application, resource, node, **kwargs)
        self.assertStatus(r_put, status)

        # if PUTting succeed, check that document is there and equals to resource

        if self.invariant_check and succeed(r_put):
            r_get = self.get(application, node, status=None, client=client)
            self.assertStatus(r_get, 200,
                              'although PUT succeed, following GET on the same URI did not: %s %s' % \
                              (r_get.code, r_get.msg))
            self.assertEqual(resource.strip(), r_get.body) # is body put equals to body got?
            if content_type_in_GET is not None:
                self.assertHeader(r_get, 'content-type', content_type_in_GET)

        return r_put

    def put_new(self, application, resource, node=None,
                status=201, content_type_in_GET=None, client=None):
        # QQQ use If-None-Match or some other header to do that without get
        self.get(application, node=node, status=404, client=client)
        return self.put(application, resource, node, status, content_type_in_GET, client)

    def delete(self, application, node=None, status=200, client=None, **kwargs):
        client = client or self.client
        r = client.delete(application, node, **kwargs)
        self.assertStatus(r, status)

        # if deleting succeed, GET should return 404
        if self.invariant_check and succeed(r) or r.code == 404:
            r_get = self.get(application, node, status=None)
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


def loadSuiteFromModule(module, option_parser):
    if isinstance(module, basestring):
        module = sys.modules[module]
    suite = TestLoader().loadTestsFromModule_wparser(module, option_parser)
    return suite

def run_suite(suite, options, args):
    if hasattr(suite, 'initialize'):
        suite.initialize(options, args)

    if options.debug:
        try:
            suite.debug()
        except Exception, ex:
            print '%s: %s' % (ex.__class__.__name__, ex)
            for x in dir(ex):
                attr = getattr(ex, x)
                if x[:1]!='_' and not callable(attr):
                    print '%s: %r' % (x, attr)
            raise
    else:
        unittest.TextTestRunner(verbosity=2).run(suite)

def check_options(options):
    xcaplib.xcapclient.check_options(options)
    if hasattr(options, 'debug') and options.debug:
        HTTPConnectionWrapper.debug = True

def runSuiteFromModule(module='__main__'):
    read_xcapclient_cfg()
    option_parser = OptionParser(conflict_handler='resolve')
    suite = loadSuiteFromModule(module, option_parser)
    option_parser.add_option('-d', '--debug', action='store_true', default=False)
    options, args = option_parser.parse_args()
    check_options(options)
    run_suite(suite, options, args)
