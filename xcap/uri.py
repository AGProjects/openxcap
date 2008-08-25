"""XCAP URI module

http://tools.ietf.org/html/rfc4825#section-6
"""

import re
import urllib
from copy import copy
from xml.sax.saxutils import quoteattr

from application.configuration import *
from application import log

from xcap.errors import *

XPATH_DEFAULT_PREFIX = 'default' # should be more random


class XCAPUser(object):
    """XCAP ID."""

    def __init__(self, user_id):
        if user_id.startswith("sip:"):
            user_id = user_id[4:]
        _split = user_id.split('@', 1)
        self.username = _split[0]
        if len(_split) == 2:
            self.domain = _split[1]
        else:
            self.domain = None
        self.uri = 'sip:%s@%s' % (self.username, self.domain)

    def __eq__(self, other):
        return isinstance(other, XCAPUser) and self.username == other.username and self.domain == other.domain

    def __ne__(self, other):
        return not self.__eq__(other)

    def __nonzero__(self):
        return bool(self.username) and bool(self.domain)

    def __str__(self):
        return "%s@%s" % (self.username, self.domain)


class Str(str):
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str.__repr__(self))

class TerminalSelector(Str):
    pass
    
class AttributeSelector(TerminalSelector):

    def __init__(self, s):
        assert s[0] == '@', s
        self.attribute = s[1:]

    
class NamespaceSelector(TerminalSelector):
    pass

class StepParsingError(ValueError):
    pass


def parse_qname(qname, defnamespace, namespaces):
    if qname == '*':
        return qname
    try:
        prefix, name = qname.split(':')
    except ValueError:
        return (defnamespace, qname)
    else:
        return (namespaces[prefix], name)


class Step(Str):
    """
    >>> x = Step('list')
    >>> x.name, x.position, x.att_name, x.att_value
    ((None, 'list'), None, None, None)

    >>> x = Step('list[3]')
    >>> x.name, x.position, x.att_name, x.att_value
    ((None, 'list'), 3, None, None)

    >>> x = Step('list[@name="other"]')
    >>> x.name, x.position, x.att_name, x.att_value
    ((None, 'list'), None, (None, 'name'), 'other')

    >>> x = Step('el1[3][@att="third"]')
    >>> x.name, x.position, x.att_name, x.att_value
    ((None, 'el1'), 3, (None, 'att'), 'third')

    >>> x = Step('*[2]')
    >>> x.name, x.position, x.att_name, x.att_value
    ('*', 2, None, None)

    >>> x = Step('el1[]')
    Traceback (most recent call last):
     ...
    StepParsingError: cannot parse: 'el1[]'

    >>> x = Step('el1[3][]')
    Traceback (most recent call last):
     ...
    StepParsingError: cannot parse: 'el1[3][]'

    >>> x = Step('el1[3][@att]')
    Traceback (most recent call last):
     ...
    StepParsingError: cannot parse: 'el1[3][@att]'

    >>> x = Step('el1[3][@att=third]')
    Traceback (most recent call last):
     ...
    StepParsingError: att-value must be quoted with '' or "": 'el1[3][@att=third]'

    >>> x = Step('a:from_a[2][@b:att="third"]', '', {'a' : 'name:space:a', 'b' : 'name:space:b'})
    >>> x.name, x.position, x.att_name, x.att_value
    (('name:space:a', 'from_a'), 2, ('name:space:b', 'att'), 'third')

    >>> x = Step('from_a[2][@att="third"]', 'name:space:a')
    >>> x.name, x.position, x.att_name, x.att_value
    (('name:space:a', 'from_a'), 2, (None, 'att'), 'third')

    #(('name:space:a', 'from_a'), 2, ('name:space:a', 'att'), 'third')
    """

    pattern = '^(?P<name>[^\\[]+)(\\[(?P<position>\d+)\\])?(\\[@(?P<attrtest>[^=]+=[^\\]]+)\\])?$'
    pattern = re.compile(pattern)

    def __new__(cls, s, namespace=None, namespaces={}):
        return Str.__new__(cls, s)

    def __init__(self, s, namespace=None, namespaces={}):
        m = self.pattern.match(s)
        if not m:
            raise StepParsingError('cannot parse: %r' % s)

        d = m.groupdict()
        name = d['name']
        self.name = parse_qname(name, namespace, namespaces)

        self.position = d.get('position')
        if self.position is not None:
            self.position = int(self.position)
            
        attrtest = d.get('attrtest')
        if attrtest:
            att_name, value = attrtest.split('=', 1)
            if len(value)<2 or value[0]!=value[-1] or value[0] not in '"\'':
                raise StepParsingError('att-value must be quoted with \'\' or "": %r' % s)
            # XML attributes don't belong to the same namespace as containing tag?
            # because thats what I get in startElement/attrs.items - (None, 'tag')
            # lxml's xpath works similar way too:
            # doc.xpath('/default:rls-services/defaultg:service[@uri="sip:mybuddies@example.com"]',
            #           namespaces = {'default':"urn:ietf:params:xml:ns:rls-services"})
            # works, while 
            # doc.xpath('/default:rls-services/defaultg:service[@default:uri="sip:mybuddies@example.com"]',
            #           namespaces = {'default':"urn:ietf:params:xml:ns:rls-services"})
            # does not
            self.att_name  = parse_qname(att_name, None, namespaces)
            self.att_value = value[1:-1]
        else:
            self.att_name  = None
            self.att_value = None


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
            namespace2prefix = prefixes[namespace]
        else:
            prefix = None
        if prefix:
            res += '[@%s:%s="%s"]' % (prefix, name, quoteattr(step.att_value))
        else:
            res += '[@%s=%s]' % (name, quoteattr(step.att_value))
    return res


class ElementSelector(list):
    """
    >>> x = ElementSelector('watcherinfo/watcher-list/watcher[@id="8ajksjda7s"]')
    >>> x
    [Step('watcherinfo'), Step('watcher-list'), Step('watcher[@id="8ajksjda7s"]')]

    >>> print x
    /watcherinfo/watcher-list/watcher[@id="8ajksjda7s"]

    """

    def __init__(self, s, namespace=None, namespaces={}):
        steps = [Step(x, namespace, namespaces) for x in s.strip('/').split('/')]
        list.__init__(self, steps)
        self.namespace = namespace

    def __str__(self):
        return '/' + '/'.join(str(x) for x in self)

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


class NodeSelector(Str):
    """
    >>> x = NodeSelector('watcherinfo/watcher-list/watcher[@id="8ajksjda7s"]')
    >>> print x.element_selector
    /watcherinfo/watcher-list/watcher[@id="8ajksjda7s"]
    >>> x.terminal_selector is None
    True
    
    >>> x = NodeSelector('/resource-lists/list[@name="other"]/@some-attribute')
    >>> print x.element_selector
    /resource-lists/list[@name="other"]
    >>> x.terminal_selector
    AttributeSelector('@some-attribute')

    >>> x.terminal_selector.attribute
    'some-attribute'

    >>> x = NodeSelector('/resource-lists/list[@name="friends"]/namespace::*')
    >>> print x.element_selector
    /resource-lists/list[@name="friends"]
    >>> x.terminal_selector
    NamespaceSelector('namespace::*')

    >>> x = NodeSelector('/resource-lists/list[@name="friends"]/@name')
    """

    XMLNS_REGEXP = re.compile("xmlns\((?P<nsdata>.*?)\)")
    
    def __new__(cls, selector, _namespace=None):
        return Str.__new__(cls, selector)

    def __init__(self, selector, namespace=None):
        sections = selector.split('?', 1)

        if len(sections) == 2: ## a query component is present
            self.ns_bindings = self._parse_query(sections[1])
        else:
            self.ns_bindings = {}

        element_selector, terminal = sections[0].rsplit('/', 1)

        if terminal.startswith('@'):
            self.terminal_selector = AttributeSelector(terminal)
        elif terminal == 'namespace::*':
            self.terminal_selector = NamespaceSelector(terminal)
        else:
            element_selector += '/' + terminal
            self.terminal_selector = None

        self.element_selector = ElementSelector(element_selector, namespace, self.ns_bindings)

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
                log.error("Ignoring invalid XPointer XMLNS expression: %s" % m)
                continue
        return ns_bindings

    def replace_default_prefix(self, defprefix=XPATH_DEFAULT_PREFIX, append_terminal = True):
        namespace2prefix = dict((v, k) for (k, v) in self.ns_bindings)
        namespace2prefix[self.element_selector.namespace] = defprefix
        res = self.element_selector.replace_default_prefix(namespace2prefix)
        if append_terminal and self.terminal_selector:
            res += '/' + self.terminal_selector
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
        if not isinstance(selector, str):
            raise TypeError("Document Selector must be a string")
        segments  = selector.split('/')
        if not segments[0]: ## ignore first '/'
            segments.pop(0)
        if not segments[-1]: ## ignore last '/' if present
            segments.pop()
        if len(segments) < 2:
            raise ValueError("invalid Document Selector")
        self.application_id = segments[0]
        self.context = segments[1]     ## either "global" or "users"
        if self.context not in ("users", "global"):
            raise ValueError("the Document Selector context must be 'users' or 'global': '%s'" % self.context)
        self.user_id = None
        if self.context == "users":
            self.user_id = segments[2]
            segments = segments[3:]
        else:
            segments = segments[2:]
        if not segments:
            raise ValueError("invalid Document Selector: missing document's path")
        self.document_path = '/'.join(segments)


class XCAPUri(object):
    """An XCAP URI containing the XCAP root, document selector and node selector."""

    node_selector_separator = "~~"

    def __init__(self, xcap_root, resource_selector, default_realm='example.com', namespaces = {}):
        "namespaces maps application id to default namespace"
        self.xcap_root = xcap_root
        self.resource_selector = resource_selector
        realm = default_realm
        # convention to get the realm if it's not contained in the user ID section
        # of the document selector (bad eyebeam)
        if self.resource_selector.startswith("@"):
            first_slash = self.resource_selector.find("/")
            realm = self.resource_selector[1:first_slash]
            self.resource_selector = self.resource_selector[first_slash:]
        _split = self.resource_selector.split(self.node_selector_separator, 1)
        doc_selector = _split[0]
        try:
            self.doc_selector = DocumentSelector(doc_selector)  ## the Document Selector
        except (TypeError, ValueError), e:
            log.error("Invalid Document Selector %s (%s)" % (doc_selector, str(e)))
            raise ResourceNotFound(str(e))
        self.application_id = self.doc_selector.application_id
        if len(_split) == 2:                             ## the Node Selector
            self.node_selector = NodeSelector(urllib.unquote(_split[1]), namespaces.get(self.application_id))
        else:
            self.node_selector = None
        self.user = self.doc_selector.user_id and XCAPUser(self.doc_selector.user_id)
        if not self.user.domain:
            self.user.domain = realm

    def __str__(self):
        return self.xcap_root + self.resource_selector


if __name__=='__main__':
    import doctest
    doctest.testmod()
