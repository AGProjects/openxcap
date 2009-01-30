import sys
import os
import unittest
import re
import types
import socket
import time
import traceback
from optparse import OptionParser, SUPPRESS_HELP
from lxml import etree
from copy import copy
from ConfigParser import SafeConfigParser as ConfigParser

xcaplib_min_version = (1, 0, 8)

sys.path.append('../../../python-xcaplib')
import xcaplib
try:
    xcaplib.version_info
except AttributeError:
    raise ImportError('Need python-xcaplib of version at least %s.%s.%s' % xcaplib_min_version)

if xcaplib.version_info[:3]<xcaplib_min_version:
    raise ImportError('Need python-xcaplib of version at least %s.%s.%s, you have %s.%s.%s' % \
                      (xcaplib_min_version + xcaplib.version_info[:3]))

from xcaplib import xcapclient
del sys.path[-1]


apps = ['pres-rules',
        'org.openmobilealliance.pres-rules',
        'resource-lists',
        'pidf-manipulation',
        'watchers',
        'rls-services',
        'test-app',
        'xcap-caps']

def succeed(r):
    return 200 <= r.status <= 299

class XCAPTest(unittest.TestCase):

    # if true, each PUT or DELETE will be followed by GET to ensure that it has indeed succeeded
    invariant_check = True

    @classmethod
    def setupOptionParser(cls, parser):
        xcapclient.setup_parser_client(parser)

    def initialize(self, options, args = []):
        if not hasattr(self, '_options'):
            self._options = copy(options)
        if not hasattr(self, '_args'):
            self._args = copy(args)

    def new_client(self):
        return xcapclient.make_xcapclient(self.options)

    def update_client_options(self):
        self.client = self.new_client()

    def setUp(self):
        self.options = copy(self._options)
        self.args = copy(self._args)
        self.update_client_options()

    def assertStatus(self, r, status, msg=None):
        if status is None:
            return
        elif isinstance(status, int):
            if r.status != status:
                if msg is None:
                    msg = 'Status (%s) != %s' % (r.status, status)
                raise self.failureException(msg)
        else:
            ## status is a tuple or a list
            if r.status not in status:
                if msg is None:
                    msg = 'Status (%s) not in %s' % (r.status, str(status))
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
        return r.etag

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
        r = client._get(application, node, **kwargs)
        self.validate_error(r, application)
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
        r_put = client._put(application, resource, node, **kwargs)
        self.validate_error(r_put, application)
        self.assertStatus(r_put, status)

        # if PUTting succeed, check that document is there and equals to resource

        if self.invariant_check and succeed(r_put):
            r_get = self.get(application, node, status=None, client=client)
            self.assertStatus(r_get, 200,
                              'although PUT succeed, following GET on the same URI did not: %s %s' % \
                              (r_get.status, r_get.reason))
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
        r = client._delete(application, node, **kwargs)
        self.validate_error(r, application)
        self.assertStatus(r, status)

        # if deleting succeed, GET should return 404
        if self.invariant_check and succeed(r) or r.status == 404:
            r_get = self.get(application, node, status=None)
            self.assertStatus(r_get, 404,
                              'although DELETE succeed, following GET on the same URI did not return 404: %s %s' % \
                              (r_get.status, r_get.reason))
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

    def validate_error(self, r, application):
        if r.status==409 or r.headers.gettype()=='application/xcap-error+xml':
            self.assertEqual(r.headers.gettype(), 'application/xcap-error+xml')
            xml = validate_xcaps_error(r.body)
            if '<uniqueness-failure' in r.body:
                namespaces={'d': 'urn:ietf:params:xml:ns:xcap-error'}
                field = xml.xpath('/d:xcap-error/d:uniqueness-failure/d:exists/@field', namespaces=namespaces)
                assert len(field)==1, r.body


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


def validate(document, schema):
    parser = etree.XMLParser(schema = schema)
    return etree.fromstring(document, parser)

def open_schema(filename):
    my_dir = os.path.dirname(os.path.abspath(__file__))
    return file(os.path.join(my_dir, 'schemas', filename))

def load_schema(filename):
    return etree.XMLSchema(etree.parse(open_schema(filename)))

xcaps_error_schema = load_schema('xcap-error.xsd')

def validate_xcaps_error(document):
    xml = validate(document, xcaps_error_schema)
    root_tag = xml.xpath('/x:xcap-error', namespaces={'x': 'urn:ietf:params:xml:ns:xcap-error'})
    assert len(root_tag)==1, root_tag
    return xml

def prepare_optparser(option_parser=None):
    if option_parser is None:
        option_parser = OptionParser(conflict_handler='resolve')
    option_parser = OptionParser(conflict_handler='resolve')
    option_parser.add_option('-d', '--debug', action='store_true', default=False)
    option_parser.add_option('-r', '--repeat', type='int', default=1, help='default is 1. use -1 to loop forever')

    # Fix xcaplib to use non-blocking sockets from eventlet.green package
    option_parser.add_option('-c', '--client', default='xcaplib', help=SUPPRESS_HELP)

    # Start OpenXCAP server in-process. You should also use --eventlet option then.
    option_parser.add_option('--start-server', metavar='CONFIG_FILE', help=SUPPRESS_HELP)
    return option_parser

def process_options(options):
    xcapclient.update_options_from_config(options)
    if options.client == 'xcapclient':
        import xcapclientwrap
        XCAPTest.new_client = lambda self: xcapclientwrap.make_client(self.options)
    else:
        if options.client == 'eventlet':
            def new_client(self):
                enable_eventlet()
                return xcapclient.make_xcapclient(self.options)
            XCAPTest.new_client = new_client
        else:
            assert options.client == 'xcaplib', `options.client`
    if options.start_server is not None:
        options.server = InProcessServer(options)
    else:
        options.server = RemoteServer(options)

def run_command(command, options):
    options.server.start()
    try:
        n = options.repeat
        while n!=0:
            n -= 1
            try:
                command()
            except Exception:
                traceback.print_exc()
                if n==0:
                    raise
    finally:
        options.server.stop()

def runSuiteFromModule(module='__main__'):
    option_parser = prepare_optparser()
    suite = loadSuiteFromModule(module, option_parser)
    options, args = option_parser.parse_args()
    process_options(options)
    run_command(lambda : run_suite(suite, options, args), options)


class RemoteServer:

    def __init__(self, options):
        self.options = options

    def start(self):
        xcapclient.validate_client_configuration(self.options)

    def stop(self):
        pass

class InProcessServer:

    def __init__(self, options):
        parser = ConfigParser()
        self.config_filename = options.start_server
        parser.read(self.config_filename)
        self.root = parser.get('Server', 'root')
        port = parser.get('Server', 'port')
        if port is not None:
            self.root += ':' + port
        options.xcap_root = self.root
        if not options.sip_address:
            options.sip_address = 'alice@example.com'
        if not options.password:
            options.password = '123'

    def start(self):
        print 'STARTING SERVER on %s' % self.root
        start_server(file(self.config_filename))

    def stop(self):
        from twisted.internet import reactor
        reactor.callLater(0, reactor.stop)
        from eventlet.api import get_hub
        get_hub().switch()

def enable_eventlet():
    from eventlet.green import urllib2, socket as greensocket, time as greentime
    from xcaplib import httpclient
    # replacing all the references to the old urllib2 in xcaplib:
    httpclient.urllib2 = urllib2
    httpclient.HTTPRequest.__bases__ = (urllib2.Request,)
    global socket, time
    socket = greensocket
    time = greentime


def start_server(config_file):
    from application import log # to print log.msg messages to stdout
    sys.path = ['../..'] + sys.path
    import xcap
    xcap.__cfgfile__ = config_file
    from xcap.logutil import start_log
    start_log()
    from xcap.server import XCAPServer
    class Server(XCAPServer):
        def run(self, reactor):
            pass
    server = Server()
    server.start()
    return server

