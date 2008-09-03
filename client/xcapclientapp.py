#!/usr/bin/env python
"""
  %prog: manage XCAP documents
  %prog [OPTIONS] --app AUID ACTION [NODE-SELECTOR]

  ACTION is an operation to perform: get, put or delete.
  Presence of NODE-SELECTOR indicates that action is to be performed on an
  element or an attribute.
"""

import sys

OPT_COMPLETE = '--print-completions'

try:
    import os
    import optparse
    import traceback
    from StringIO import StringIO
    from xml.sax.saxutils import quoteattr
    from lxml import etree; 
    from twisted.python import log as twistedlog
    
    # prevent application.configuration from installing its SimpleObserver
    # which prints to stdout all kinds of useless crap from twisted
    twistedlog.defaultObserver = None
    
    from application.configuration import *
    from xcapclient import *
except:
    if OPT_COMPLETE in sys.argv[-2:]:
        sys.exit(1)
    else:
        raise

# to guess app from /NODE-SELECTOR
app_by_root_tag = {
    #root tag        :  app,
    'resource-lists' : 'resource-lists',
    'rls-services'   : 'rls-services',
    'ruleset'        : 'pres-rules',
    'presence'       : 'pidf-manipulation',
    'watchers'       : 'watchers',
    'xcap-caps'      : 'xcap-caps'}

root_tags = ['/' + root_tag for root_tag in app_by_root_tag.keys()]
del root_tag

logfile = None
#logfile = file('./xcapclient.log', 'a+')

def log(s, *args, **kwargs):
    if logfile:
        s = str(s)
        if args:
            s = s % args
        if kwargs:
            s = s % kwargs
        logfile.write(s + '\n')

class OptionParser_NoExit(optparse.OptionParser):
    "raise ValueError instead of killing the process with error message"
    # no need for error messages in completion
    def error(self, msg):
        raise ValueError(msg)

class ServerConfig(ConfigSection):
    _datatypes = {'root': lambda x: ServerConfig.root + x.split()}
    root = []

class User:

    def __init__(self, uri):
        user, self.domain = uri.split('@', 1)
        if ':' in user:
            self.username, self.password = user.split(':', 1)
        else:
            self.username = user
            self.password = None

    def __str__(self):
        if self.password is None:
            return '%s@%s' % (self.username, self.domain)
        else:
            return '%s:%s@%s' % (self.username, self.password, self.domain)

    def without_password(self):
        return '%s@%s' % (self.username, self.domain)


class Auth:

    def __new__(cls, auth):
        if auth.lower() == 'none':
            return None
        else:
            return auth.lower()


class ClientConfig(ConfigSection):
    _datatypes = {
        'user' : lambda x: ClientConfig.user + [User(y) for y in x.split()],
        'auth' : Auth }
    user = []
    auth = 'basic'

def read_xcapclient_cfg():
    client_config = ConfigFile(os.path.expanduser('~/.xcapclient'))
    client_config.read_settings('Client', ClientConfig)
    client_config.read_settings('Server', ServerConfig)

def read_openxcap_cfg():
    # load local server's xcap-root as well
    server_config = ConfigFile('/etc/openxcap/config.ini')
    server_config.read_settings('Server', ServerConfig)

def read_cfg():
    read_xcapclient_cfg()
    read_openxcap_cfg()


def setup_parser_client(parser):

    help = 'XCAP root'
    if ServerConfig.root:
        help += '; %s is default' % ServerConfig.root[0]
        default = ServerConfig.root[0]
    else:
        help += ', e.g. http://xcap.example.com/xcap-root'
        default = None
    parser.add_option("--root", help=help, default=default)

    help = 'user id in format username[:password]@domain'
    if ClientConfig.user:
        help += ', %s is default' % ClientConfig.user[0]
        default = ClientConfig.user[0]
    else:
        default = None
    parser.add_option("--user", help=help, default=default)

    help="authentification type, basic, digest or none; " + \
         "%s is default when password is present, none when it's not" % ClientConfig.auth

    parser.add_option("--auth", help=help, default=ClientConfig.auth)


def make_xcapclient(options, XCAPClient=XCAPClient):
    return XCAPClient(options.root, options.user.without_password(),
                      options.user.password, options.auth)

def setup_parser(parser):
    help="Application Unique ID. There's no default value; however, it will be " + \
         "guessed from NODE-SELECTOR (when present) or from the input file (when action is PUT). " + \
         "Known apps: %s." % ', '.join(apps)
    parser.add_option("--app", dest='app', help=help)

    setup_parser_client(parser)

    parser.add_option("-i", dest='input',
                      help="source file for the PUT request; <stdin> is default")
    parser.add_option("-o", dest='output',
                      help="output file for the server response (successful or rejected); <stdout> is default")
    parser.add_option("-d", dest='debug', action='store_true', default=False,
                      help="print whole http requests and replies to stderr")

def lxml_tag(tag):
    # for tags like '{namespace}tag'
    if '}' in tag:
        namespace, tag = tag.split('}')
        namespace = namespace[1:]
        return namespace, tag
    return None, tag

def get_app_by_input_root_tag(root_tag):
    return app_by_root_tag.get(lxml_tag(root_tag)[1])

apps = app_by_root_tag.values() + ['test-app']

class NullObserver(twistedlog.DefaultObserver):
    def _emit(self, eventDict):
        if eventDict['isError']:
            if eventDict.has_key('failure'):
                text = eventDict['failure'].getTraceback()
            else:
                text = ' '.join([str(m) for m in eventDict['message']]) + '\n'
            logfile.write(text)
            logfile.flush()
        else:
            text = ' '.join([str(m) for m in eventDict['message']]) + '\n'
            logfile.write(text)
            logfile.flush()

wordbreaks = '"\'><=;|&(:' # $COMP_WORDBREAKS

def bash_quote(s):
    return "'" + s + "'"

def bash_escape(s):
    if s[0]=="'":
        return s # already quoted
    for c in wordbreaks:
        s = s.replace(c, '\\' + c)
    return s

def bash_unquote(s):
    if s and s[0]=="'":
        s = s[1:]
        if s and s[-1]=="'":
            s = s[:-1]
        return s
    for c in wordbreaks:
        s = s.replace('\\' + c, c)
    return s


# result is passed as a parameter, since in this case partial
# result is better than no result at all
def completion(result, argv, comp_cword):

    log("argv: %r", argv)
    
    if twistedlog.defaultObserver is not None:
        twistedlog.defaultObserver.stop()
        twistedlog.defaultObserver = NullObserver()
        twistedlog.defaultObserver.start()

    if len(argv)==comp_cword:
        current, argv = argv[-1], argv[:-1]
    else:
        current = ''

    argv = [bash_unquote(x) for x in argv]
    current_unq = bash_unquote(current)

    def add(*args):
        for x in args:
            x = bash_escape(str(x))
            if x.startswith(current):
                result.add(x)

    def add_quoted(*args):
        for x in args:
            x = bash_quote(str(x))
            if x.startswith(current):
                result.add(x)

    if current:
        if current[0]=="'":
            add = add_quoted
        else:
            add_quoted = add

    def discard(*args):
        for x in args:
            result.discard(x)

    log('current=%r argv=%r', current, argv)

    def complete_options(parser):
        for option in parser.option_list:
            for opt in option._short_opts + option._long_opts:
                add(opt)
        add('put', 'get', 'delete')

    read_cfg()
    parser = OptionParser_NoExit()
    setup_parser(parser)

    if not argv:
        return complete_options(parser)

    if argv[-1]=='--app':
        return add(*apps)
    elif argv[-1]=='--root':
        return add_quoted(*ServerConfig.root)
    elif argv[-1]=='--user':
        return add_quoted(*ClientConfig.user)
    elif argv[-1]=='--auth':
        return add('basic', 'digest', 'none')
    elif argv[-1]!='-d' and argv[-1][0]=='-':
        return

    options, args = parser.parse_args(argv)

    if not args:
        complete_options(parser)
        discard(*argv)
        discard('-h', '--help')
        if options.input is not None:
            discard('-o', 'get', 'delete')
        return

    if isinstance(options.user, basestring):
        options.user = User(options.user)

    action, args = args[0], args[1:]
    action = action.lower()

    if args:
        return

    if options.app:
        return add_quoted(*complete_xpath(options, options.app, current_unq))
    else:
        try:
            root_tag, rest = current_unq[1:].split('/', 1)
        except ValueError:
            add_quoted(*root_tags)
            for x in root_tags:
                add_quoted(x + '/')
        else:
            # get/delete: GET the document, get all the path
            # put: GET the document, get all the paths
            #      read input document, get all the insertion points
            return add_quoted(*complete_xpath(options, app_by_root_tag[root_tag], current_unq))


def run_completion(option, raise_ex=False):
    result = set()
    try:
        if sys.argv[-1]==option:
            completion(result, sys.argv[1:-1], len(sys.argv))
        if sys.argv[-2]==option:
            completion(result, sys.argv[1:-2], int(sys.argv[-1]))
    except:
        if raise_ex:
            raise
        else:
            log(traceback.format_exc())
    finally:
        for x in result:
            log(x)
            print x


def fix_namespace_prefix(selector, prefix = 'default'):
    if not selector:
        return ''
    steps = []
    for step in selector.split('/'):
        if not step or ':' in step[:step.find('[')]:
            steps.append(step)
        else:
            steps.append(prefix + ':' + step)
    return '/'.join(steps)

def path_element((prefix, name)):
    if prefix:
        return prefix + ':' + name
    else:
        return name

def enumerate_paths(document, selector_start):
    log('enumerate_paths(%r, %r)', document[:10], selector_start)

    rejected = set()
    added = set()
    def add(x):
        if x in rejected:
            return
        if x in added:
            added.discard(x)
            rejected.add(x)
        else:
            added.add(x)
    
    x = selector_start.rfind('/')
    parent, current = selector_start[:x], selector_start[x:]
    xml = etree.parse(StringIO(document))
    namespaces = xml.getroot().nsmap.copy()
    namespaces['default'] = namespaces[None]
    del namespaces[None]

    log('parent=%r current=%r', parent, current)
    
    if not parent:
        x = '/' + lxml_tag(xml.getroot().tag)[1]
        return [x, x+'/']
    else:
        log('xpath argument: %s', fix_namespace_prefix(parent))
        elements = xml.xpath(fix_namespace_prefix(parent), namespaces=namespaces)
        log('xpath result: %s', elements)

    if len(elements)!=1:
        return []

    prefixes = dict((v, k) for (k, v) in xml.getroot().nsmap.iteritems())
    context = etree.iterwalk(elements[0], events=("start", "end"))
    indices = {}
    star_index = 0
    it = iter(context)
    the_element = it.next()
    for (k, v) in the_element[1].attrib.items():
        add(parent + '/@' + k)
    
    skip = 0

    paths = []
    has_children = False
    
    for action, elem in it:
        log("%s %s", action, elem)
        if action == 'start':
            skip += 1
            if skip==1:
                has_children = False
                star_index += 1
                paths.append(parent + '/*[%s]' % star_index)
                namespace, tag = lxml_tag(elem.tag)
                log('namespace=%r prefixes=%r', namespace, prefixes)
                prefix = prefixes[namespace]
                el = path_element((prefix, tag))
                indices.setdefault(el, 0)
                indices[el]+=1
                paths.append(parent + '/' + el)
                paths.append(parent + '/' + el + '[%s]' % indices[el])
                for (k, v) in elem.attrib.items():
                    v = quoteattr(v)
                    paths.append(parent + '/' + el + '[@%s=%s]' % (k, v))
            else:
                has_children = True
        elif action == 'end':
            if skip == 1:
                for p in paths:
                    add(p)
                    if has_children:
                        add(p + '/')
                paths = []
            skip -= 1

    log('indices=%r', indices)
    for (tag, index) in indices.iteritems():
        if index == 1:
            added.discard(parent + '/' + tag + '[1]')
            added.discard(parent + '/' + tag + '[1]/')

    if star_index == 1:
        added.discard(parent + '/*[1]')
        #added.add(parent + '/*')
        if parent + '/*[1]/' in added:
            added.discard(parent + '/*[1]/')
            #added.add(parent + '/*/')

    for x in added:
        log('x=%r', x)

    return added


def complete_xpath(options, app, selector):
    client = XCAPClient(options.root, options.user.without_password(),
                        options.user.password, options.auth)

    result = client.get(app)

    if isinstance(result, Resource):
        return enumerate_paths(result, selector)
    return []


class IndentedHelpFormatter(optparse.IndentedHelpFormatter):
    def format_usage(self, usage):
        return usage


def check_options(options):
    if options.root is None:
        sys.exit('Please specify XCAP root with --root. You can also put the default root in ~/.xcapclient.')

    if options.user is None:
        sys.exit('Please specify userid with --user. You can also put the default userid in ~/.xcapclient.')

    if isinstance(options.user, basestring):
        options.user = User(options.user)


def parse_args():
    argv = sys.argv[1:]

    if not argv:
        sys.exit('Type %s -h for help.' % sys.argv[0])

    read_cfg()
    parser = optparse.OptionParser(usage=__doc__, formatter=IndentedHelpFormatter())
    setup_parser(parser)
    options, args = parser.parse_args(argv)

    if not args:
        sys.exit('Please provide ACTION.')

    check_options(options)
    
    action, args = args[0], args[1:]
    action = action.lower()
    if action not in ['get', 'put', 'delete']:
        sys.exit('ACTION must be either GET or PUT or DELETE.')

    options.input_data = None

    if action == 'put':
        if options.input is None:
            if hasattr(sys.stdin, 'isatty') and sys.stdin.isatty():
                sys.stderr.write('Reading PUT body from stdin. Type CTRL-D when done\n')
            options.input_data = sys.stdin.read()
        else:
            options.input_data = file(options.input).read()

    if options.output is None:
        options.output_file = sys.stdout
    else:
        options.output_file = file(options.output, 'w+')

    node_selector = None

    if args:
        node_selector, args = args[0], args[1:]
        if node_selector[0]!='/':
            node_selector = '/' + node_selector
        if not options.app:
            root_tag = node_selector.split('/')[1]
            options.app = app_by_root_tag.get(root_tag)
            if not options.app:
                sys.exit('Please specify --app. Root tag %r gives no clue.' % root_tag)

    if not options.app:
        if action == 'put':
            root_tag = get_root_tag(options.input_data)
            if root_tag is None:
                sys.exit('Please specify --app. Cannot extract root tag from document %r.' % \
                         (options.input or '<stdin'))
            options.app = get_app_by_input_root_tag(root_tag)
            if options.app is None:
                sys.exit('Please specify --app. Root tag %r gives in the document %r gives no clue.' % \
                         (root_tag, options.input))
        else:
            sys.exit('Please specify --app or NODE-SELECTOR')

    if args:
        sys.exit("Too many positional arguments.")

    return options, action, node_selector


def write_body(options, data, etag, print_zero_length=False):
    if etag is not None:
        sys.stderr.write('etag: %s\n' % etag)
    if data or print_zero_length:
        sys.stderr.write('content-length: %s\n' % len(data))
    if data:
        options.output_file.write(data)
        options.output_file.flush()
        if options.output: # i.e. not stdout
            sys.stderr.write('%s bytes saved to %s\n' % (len(data), options.output))
        else:
            if data and data[-1]!='\n':
                sys.stderr.write('\n')       

def main():

    if OPT_COMPLETE in sys.argv[-2:]:
        return run_completion(OPT_COMPLETE)
    elif '--debug-completions' in sys.argv[-2:]:
        return run_completion('--debug-completions', raise_ex=True)

    options, action, node_selector = parse_args()
    client = make_xcapclient(options)
    sys.stderr.write('url: %s\n' % client.get_url(options.app, node_selector))

    try:
        if action == 'get':
            result = client.get(options.app, node_selector)
        elif action == 'delete':
            result = client.delete(options.app, node_selector)
        elif action == 'put':
            result = client.put(options.app, options.input_data, node_selector)
    except HTTPError, ex:
        result = ex

    if isinstance(result, Resource):
        write_body(options, result, result.etag, print_zero_length=True)
        assert action == 'get', action
    elif isinstance(result, addinfourl):
        sys.stderr.write('%s %s\n' % (result.code, result.msg))
        write_body(options, result.read(), result.headers.get('etag')) 
    else:
        sys.exit('%s: %s' % (result.__class__.__name__, result))

if __name__ == '__main__':
    main()
