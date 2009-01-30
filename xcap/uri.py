"""XCAP URI module

http://tools.ietf.org/html/rfc4825#section-6

The algorithm to decode the URI is as following:

 * First, percent-decode the whole URI (urllib.unquote)
 * Split document selector from node selector (str.split('~~'))
 * Then use xpath_tokenizer from lxml to parse the whole node selector
   and extract individual steps

Although after doing percent-decoding first, we cannot use s.split('/'),
using lexer from lxml alleviates that fact a bit and produces good results.

A potential problem can arise with URIs that contain [percent-encoded] double quotes.
Here's an example:

/resource-lists/list[@name="friends"]/external[@anchor="/list[@name=%22mkting%22]"]

which would be converted to

/resource-lists/list[@name="friends"]/external[@anchor="/list[@name="mkting"]"]

and that would confuse the parser.

I'm not sure if it's legal to have such URIs, but if it is this module has to be fixed.
Meanwhile, the safe approach is to use &quot;

/resource-lists/list[@name="friends"]/external[@anchor="/list[@name=&quot;mkting&quot;]"]

"""

import re
from urllib import unquote

from copy import copy
from xml.sax.saxutils import quoteattr
from lxml import _elementpath as ElementPath

from application import log


XPATH_DEFAULT_PREFIX = 'default' # should be more random

class Error(ValueError):
    "Base class for all errors in this module"

class NodeParsingError(Error):
    http_error = 400

class DocumentSelectorError(Error):
    http_error = 404


class XCAPUser(object):
    """XCAP ID."""

    def __init__(self, username, domain):
        self.username = username
        self.domain = domain

    @property
    def uri(self):
        return 'sip:%s@%s' % (self.username, self.domain)

    def __eq__(self, other):
        return isinstance(other, XCAPUser) and self.uri == other.uri

    def __ne__(self, other):
        return not self.__eq__(other)

    def __nonzero__(self):
        return bool(self.username) and bool(self.domain)

    def __str__(self):
        return "%s@%s" % (self.username, self.domain)

    def __repr__(self):
        return 'XCAPUser(%r, %r)' % (self.username, self.domain)

    @classmethod
    def parse(cls, user_id, default_domain=None):
        if user_id.startswith("sip:"):
            user_id = user_id[4:]
        _split = user_id.split('@', 1)
        username = _split[0]
        if len(_split) == 2:
            domain = _split[1]
        else:
            domain = default_domain
        return cls(username, domain)

# XXX currently equivalent but differently encoded URIs won't be considered equal.
def unquote_attr_value(s):
    if len(s)>1 and s[0]==s[-1] and s[0] in '"\'':
        # what about &quot; and friends?
        return s[1:-1]
    raise NodeParsingError

def xpath_tokenizer(p):
    """
    >>> xpath_tokenizer('resource-lists')
    ['resource-lists']

    >>> xpath_tokenizer('list[@name="friends"]')
    ['list', '[', '@', 'name', '=', 'friends', ']']

    We cannot properly tokenize an URI like this :(
    >>> uri_ugly = 'external[@anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list[@name="mkting"]"]'
    >>> len(xpath_tokenizer(uri_ugly)) # expected 7
    10

    To feed such URI to this function, replace quote \" with &quot;
    >>> uri_nice = 'external[@anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list[@name=&quot;mkting&quot;]"]'
    >>> len(xpath_tokenizer(uri_nice)) # expected 7
    7
    """
    out = []
    prev = None
    for op, tag in ElementPath.xpath_tokenizer(p):
        if prev == '=':
            unq = unquote_attr_value
        else:
            unq = lambda x:x
        if op:
            x = Op(unq(op))
        else:
            x = Tag(unq(tag))
        out.append(x)
        prev = x
    return out

class Op(str):
    tag = False

class Tag(str):
    tag = True


class TerminalSelector(object):
    pass


class AttributeSelector(TerminalSelector):

    def __init__(self, attribute):
        self.attribute = attribute

    def __str__(self):
        return '@' + self.attribute

    def __repr__(self):
        return 'AttributeSelector(%r)' % self.attribute


class NamespaceSelector(TerminalSelector):

    def __str__(self):
        return "namespace::*"
    
    def __repr__(self):
        return 'NamespaceSelector()'


class Str(str):
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str.__repr__(self))

def parse_qname(qname, defnamespace, namespaces):
    if qname == '*':
        return qname
    try:
        prefix, name = qname.split(':')
    except ValueError:
        return (defnamespace, qname)
    else:
        return (namespaces[prefix], name)


class Step(object):

    def __init__(self, name, position=None, att_name=None, att_value=None):
        self.name = name
        self.position = position
        self.att_name = att_name
        self.att_value = att_value

    def __repr__(self):
        args = [self.name, self.position, self.att_name, self.att_value]
        while args and args[-1] is None:
            del args[-1]
        args = [repr(x) for x in args]
        return 'Step(%s)' % ', '.join(args)


def step2str(step, namespace2prefix = {}):
    try:
        namespace, name = step.name
    except ValueError:
        res = step.name
    else:
        prefix = namespace2prefix[namespace]
        if prefix:
            res = prefix + ':' + name
        else:
            res = name

    if step.position is not None:
        res += '[%s]' % step.position

    if step.att_name is not None:
        namespace, name = step.att_name
        if namespace:
            prefix = namespace2prefix[namespace]
        else:
            prefix = None
        if prefix:
            res += '[@%s:%s=%s]' % (prefix, name, quoteattr(step.att_value))
        else:
            res += '[@%s=%s]' % (name, quoteattr(step.att_value))
    return res


def read_element_tag(lst, index, namespace, namespaces):
    if index==len(lst):
        raise NodeParsingError
    elif lst[index] == '*':
        return '*', index+1
    elif get(lst, index+1)==':':
        if not lst[index].tag:
            raise NodeParsingError
        if not get(lst, index+2) or not get(lst, index+2).tag:
            raise NodeParsingError
        return (namespaces[lst[index]], lst[index+2]), index+3
    else:
        return (namespace, lst[index]), index+1

def read_position(lst, index):
    if get(lst, index)=='[' and get(lst, index+2)==']':
        return int(lst[index+1]), index+3
    return None, index

# XML attributes don't belong to the same namespace as containing tag?
# because thats what I get in startElement/attrs.items - (None, 'tag')
# lxml's xpath works similar way too:
# doc.xpath('/default:rls-services/defaultg:service[@uri="sip:mybuddies@example.com"]',
#           namespaces = {'default':"urn:ietf:params:xml:ns:rls-services"})
# works, while 
# doc.xpath('/default:rls-services/defaultg:service[@default:uri="sip:mybuddies@example.com"]',
#           namespaces = {'default':"urn:ietf:params:xml:ns:rls-services"})
# does not
# that's why _namespace parameter is ignored and None is supplied in that case
def read_att_test(lst, index, _namespace, namespaces):
    if get(lst, index)=='[' and get(lst, index+1)=='@' and get(lst, index+3)=='=' and get(lst, index+5)==']':
        return (None, lst[index+2]), lst[index+4], index+6
    elif get(lst, index)=='[' and get(lst, index+1)=='@' and get(lst, index+3)==':' \
         and get(lst, index+5)=='=' and get(lst, index+7)==']':
        return (namespaces[lst[index+2]], lst[index+4]), lst[index+6], index+8
    return None, None, index

def get(lst, index, default=None):
    try:
        return lst[index]
    except LookupError:
        return default

def read_step(lst, index, namespace, namespaces):
    if get(lst, index)=='@':
        return AttributeSelector(lst[index+1]), index+2
    elif get(lst, index)=='namespace' and get(lst, index+1)=='::' and get(lst, index+2)=='*':
        return NamespaceSelector(), index+3
    else:
        tag, index = read_element_tag(lst, index, namespace, namespaces)
        position, index = read_position(lst, index)
        att_name, att_value, index = read_att_test(lst, index, namespace, namespaces)
        return Step(tag, position, att_name, att_value), index

def read_slash(lst, index):
    if get(lst, index)=='/':
        return index+1
    raise NodeParsingError

def read_node_selector(lst, namespace, namespaces):
    index = 0
    if get(lst, 0)=='/':
        index = read_slash(lst, index)
    steps = []
    terminal_selector = None
    while True:
        step, index = read_step(lst, index, namespace, namespaces)
        if isinstance(step, TerminalSelector):
            if index != len(lst):
                raise NodeParsingError
            terminal_selector = step
            break
        steps.append(step)
        if index == len(lst):
            break
        index = read_slash(lst, index)
    return ElementSelector(steps, namespace, namespaces), terminal_selector

def parse_node_selector(s, namespace=None, namespaces=None):
    """
    >>> parse_node_selector('/resource-lists', None, {})
    ([Step((None, 'resource-lists'))], None)
    >>> parse_node_selector('/resource-lists/list[1]/entry[@uri="sip:bob@example.com"]', None, {})
    ([Step((None, 'resource-lists')), Step((None, 'list'), 1), Step((None, 'entry'), None, (None, 'uri'), 'sip:bob@example.com')], None)
    >>> parse_node_selector('/*/list[1][@name="friends"]/@name')
    ([Step('*'), Step((None, 'list'), 1, (None, 'name'), 'friends')], AttributeSelector('name'))
    >>> parse_node_selector('/*[10][@att="val"]/namespace::*')
    ([Step('*', 10, (None, 'att'), 'val')], NamespaceSelector())
    >>> x = parse_node_selector('/resource-lists/list[@name="friends"]/external[@anchor="http://xcap.example.org/resource-lists/users/sip:a@example.org/index/~~/resource-lists/list%5b@name=%22mkting%22%5d"]')
    """
    if namespaces is None:
        namespaces = {}
    try:
        tokens = xpath_tokenizer(s)
        element_selector, terminal_selector = read_node_selector(tokens, namespace, namespaces)
        element_selector._original_string = s
        return element_selector, terminal_selector
    except NodeParsingError, ex:
        ex.args = ('Failed to parse node: %r' % s,)
        raise
    except:
        log.error('internal error in parse_node_selector(%r)' % s)
        raise


class ElementSelector(list):

    def __init__(self, lst, namespace, namespaces):
        list.__init__(self, lst)
        self.namespace = namespace
        self.namespaces = namespaces

    def replace_default_prefix(self, namespace2prefix):
        "fix string representation so it'll work with lxml xpath"
        steps = []
        for step in self:
            try:
                namespace, name = step.name
            except ValueError:
                steps.append(str(step))
            else:
                steps.append(step2str(step, namespace2prefix))
        return '/' + '/'.join(steps)

    xml_tag = re.compile('\s*<([^ >/]+)')

    def fix_star(self, element_body):
        """
        >>> elem_selector = parse_node_selector('/watcherinfo/watcher-list/*[@id="8ajksjda7s"]', None, {})[0]
        >>> elem_selector.fix_star('<watcher/>')[-1].name[1]
        'watcher'
        """
        if self and self[-1].name == '*' and self[-1].position is None:
            m = self.xml_tag.match(element_body)
            if m:
                (name, ) = m.groups()
                result = copy(self)
                result[-1].name = parse_qname(name, self.namespace, self.namespaces)
                return result
        return self


class NodeSelector(object):

    XMLNS_REGEXP = re.compile("xmlns\((?P<nsdata>.*?)\)")
    
    def __init__(self, selector, namespace=None):
        self._original_string = selector
        sections = selector.split('?', 1)

        if len(sections) == 2: ## a query component is present
            self.ns_bindings = self._parse_query(sections[1])
        else:
            self.ns_bindings = {}

        self.element_selector, self.terminal_selector = parse_node_selector(sections[0], namespace, self.ns_bindings)

    def __str__(self):
        return self._original_string

    ## http://www.w3.org/TR/2003/REC-xptr-xmlns-20030325/
    def _parse_query(self, query):
        """Return a dictionary of namespace bindings defined by the xmlns() XPointer 
           expressions from the given query."""
        ns_bindings = {}
        ns_matches = self.XMLNS_REGEXP.findall(query)
        for m in ns_matches:
            try:
                prefix, ns = m.split('=')
                ns_bindings[prefix] = ns
            except ValueError:
                log.error("Ignoring invalid XPointer XMLNS expression: %r" % m)
                continue
        return ns_bindings

    def replace_default_prefix(self, defprefix=XPATH_DEFAULT_PREFIX, append_terminal = True):
        namespace2prefix = dict((v, k) for (k, v) in self.ns_bindings)
        namespace2prefix[self.element_selector.namespace] = defprefix
        res = self.element_selector.replace_default_prefix(namespace2prefix)
        if append_terminal and self.terminal_selector:
            res += '/' + str(self.terminal_selector)
        return res

    def get_ns_bindings(self, default_ns):
        ns_bindings = self.ns_bindings.copy()
        ns_bindings[XPATH_DEFAULT_PREFIX] = default_ns
        return ns_bindings

class DocumentSelector(Str):
    """Constructs a DocumentSelector containing the application_id, context, user_id
       and document from the given selector string.
    >>> x = DocumentSelector('/resource-lists/users/sip:joe@example.com/index')
    >>> x.application_id, x.context, x.user_id, x.document_path
    ('resource-lists', 'users', 'sip:joe@example.com', 'index')

    >>> x = DocumentSelector('/rls-services/global/index')
    >>> x.application_id, x.context, x.user_id, x.document_path
    ('rls-services', 'global', None, 'index')
    """

    def __init__(self, selector):
        if selector[:1]=='/':
            selector = selector[1:]
        if selector[-1:]=='/':
            selector = selector[:-1]
        if not selector:
            raise DocumentSelectorError("Document selector does not contain auid")
        segments  = selector.split('/')
        if len(segments) < 2:
            raise DocumentSelectorError("Document selector does not contain context: %r" % selector)
        self.application_id = segments[0]
        self.context = segments[1]
        if self.context not in ("users", "global"):
            raise DocumentSelectorError("Document selector context must be either 'users' or 'global', not %r: %r" % \
                                        (self.context, selector))
        self.user_id = None
        if self.context == "users":
            try:
                self.user_id = segments[2]
            except IndexError:
                raise DocumentSelectorError('Document selector does not contain user id: %r' % selector)
            segments = segments[3:]
        else:
            segments = segments[2:]
        if not segments:
            raise DocumentSelectorError("Document selector does not contain document's path: %r" % selector)
        self.document_path = '/'.join(segments)


class XCAPUri(object):
    """An XCAP URI containing the XCAP root, document selector and node selector.

    >>> uri = XCAPUri('https://xcap.sipthor.net/xcap-root@ag-projects.com',
    ... '/resource-lists/users/sip:denis@umts.ro/properties-resource-list.xml/~~/resource-lists/list%5b@name=%22Default%22%5d/entry%5b@uri=%22sip%3adenis%40umts.ro%22%5d', {})

    >>> uri.user
    XCAPUser('denis', 'umts.ro')

    >>> uri.node_selector.element_selector
    [Step((None, 'resource-lists')), Step((None, 'list'), None, (None, 'name'), 'Default'), Step((None, 'entry'), None, (None, 'uri'), 'sip:denis@umts.ro')]

    """

    def __init__(self, xcap_root, resource_selector, namespaces):
        "namespaces maps application id to default namespace"
        self.xcap_root = xcap_root
        self.resource_selector = unquote(resource_selector)
        realm = None

        # convention to get the realm if it's not contained in the user ID section
        # of the document selector (bad eyebeam)
        if self.resource_selector.startswith("@"):
            first_slash = self.resource_selector.find("/")
            realm = self.resource_selector[1:first_slash]
            self.resource_selector = self.resource_selector[first_slash:]

        _split = self.resource_selector.split('~~', 1)

        doc_selector = _split[0]
        self.doc_selector = DocumentSelector(doc_selector)
        self.application_id = self.doc_selector.application_id
        if len(_split)==2:
            self.node_selector = NodeSelector(_split[1], namespaces.get(self.application_id))
        else:
            self.node_selector = None
        if self.doc_selector.user_id:
            self.user = XCAPUser.parse(self.doc_selector.user_id, realm)
        else:
            self.user = XCAPUser(None, realm)

    def __str__(self):
        return self.xcap_root + self.resource_selector

if __name__=='__main__':
    from xcap import __version__
    print __file__, __version__
    import sys
    if not sys.argv[1:]:
        import doctest
        doctest.testmod()
    elif sys.argv[1]=='node':
        for uri in sys.argv[2:]:
            print '%r: %s' % (uri, parse_node_selector(uri))

