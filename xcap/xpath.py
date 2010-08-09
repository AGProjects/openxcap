
# Copyright (C) 2007-2010 AG-Projects.
#


import re

from application import log
from copy import copy
from lxml import _elementpath as ElementPath
from xml.sax.saxutils import quoteattr

__all__ = ['parse_node_selector', 'AttributeSelector', 'DocumentSelector', 'ElementSelector', 'NamespaceSelector', 'NodeSelector']

# Errors

class Error(ValueError): pass

class NodeParsingError(Error):
    http_error = 400

class DocumentSelectorError(Error):
    http_error = 404


# XPath tokenizer

class List(list):
    def get(self, index, default=None):
        try:
            return self[index]
        except LookupError:
            return default

class Op(str):
    tag = False

class Tag(str):
    tag = True

class XPathTokenizer(object):

    @classmethod
    def tokens(cls, selector):
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

        def unquote_attr_value(s):
            # XXX currently equivalent but differently encoded URIs won't be considered equal (&quot, etc.)
            if len(s) > 1 and s[0] == s[-1] and s[0] in '"\'':
                return s[1:-1]
            raise NodeParsingError

        tokens = List()
        prev = None
        for op, tag in ElementPath.xpath_tokenizer(selector):
            if prev == '=':
                unq = unquote_attr_value
            else:
                unq = lambda x:x
            if op:
                x = Op(unq(op))
            else:
                x = Tag(unq(tag))
            tokens.append(x)
            prev = x
        return tokens


# XPath parsing

def read_element_tag(lst, index, namespace, namespaces):
    if index == len(lst):
        raise NodeParsingError
    elif lst[index] == '*':
        return '*', index+1
    elif lst.get(index+1) == ':':
        if not lst[index].tag:
            raise NodeParsingError
        if not lst.get(index+2) or not lst.get(index+2).tag:
            raise NodeParsingError
        try:
            namespaces[lst[index]]
        except LookupError:
            raise NodeParsingError
        return (namespaces[lst[index]], lst[index+2]), index+3
    else:
        return (namespace, lst[index]), index+1

def read_position(lst, index):
    if lst.get(index) == '[' and lst.get(index+2) == ']':
        return int(lst[index+1]), index+3
    return None, index

# XML attributes don't belong to the same namespace as containing tag
def read_att_test(lst, index, _namespace, namespaces):
    if lst.get(index) == '[' and lst.get(index+1) == '@' and lst.get(index+3) == '=' and lst.get(index+5) == ']':
        return (None, lst[index+2]), lst[index+4], index+6
    elif lst.get(index) == '[' and lst.get(index+1) == '@' and lst.get(index+3) == ':' and lst.get(index+5) == '=' and lst.get(index+7) == ']':
        return (namespaces[lst[index+2]], lst[index+4]), lst[index+6], index+8
    return None, None, index

class Step(object):

    def __init__(self, name, position=None, att_name=None, att_value=None):
        self.name = name
        self.position = position
        self.att_name = att_name
        self.att_value = att_value

    def to_string(self, ns_prefix_mapping=dict()):
        try:
            namespace, name = self.name
        except ValueError:
            res = self.name
        else:
            prefix = ns_prefix_mapping[namespace]
            if prefix:
                res = prefix + ':' + name
            else:
                res = name
        if self.position is not None:
            res += '[%s]' % self.position
        if self.att_name is not None:
            namespace, name = self.att_name
            if namespace:
                prefix = ns_prefix_mapping[namespace]
            else:
                prefix = None
            if prefix:
                res += '[@%s:%s=%s]' % (prefix, name, quoteattr(self.att_value))
            else:
                res += '[@%s=%s]' % (name, quoteattr(self.att_value))
        return res

    def __repr__(self):
        args = [self.name, self.position, self.att_name, self.att_value]
        while args and args[-1] is None:
            del args[-1]
        args = [repr(x) for x in args]
        return 'Step(%s)' % ', '.join(args)

def read_step(lst, index, namespace, namespaces):
    if lst.get(index) == '@':
        return AttributeSelector(lst[index+1]), index+2
    elif lst.get(index) == 'namespace' and lst.get(index+1) == '::' and lst.get(index+2) == '*':
        return NamespaceSelector(), index+3
    else:
        tag, index = read_element_tag(lst, index, namespace, namespaces)
        position, index = read_position(lst, index)
        att_name, att_value, index = read_att_test(lst, index, namespace, namespaces)
        return Step(tag, position, att_name, att_value), index

def read_slash(lst, index):
    if lst.get(index) == '/':
        return index+1
    raise NodeParsingError

def read_node_selector(lst, namespace, namespaces):
    index = 0
    if lst.get(0) == '/':
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

def parse_node_selector(selector, namespace=None, namespaces=dict()):
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
    try:
        tokens = XPathTokenizer.tokens(selector)
        element_selector, terminal_selector = read_node_selector(tokens, namespace, namespaces)
        element_selector._original_selector = selector
        return element_selector, terminal_selector
    except NodeParsingError, e:
        e.args = ('Failed to parse node: %r' % selector,)
        raise
    except Exception:
        log.error('internal error in parse_node_selector(%r)' % selector)
        raise


# XPath selectors

class TerminalSelector(object):
    pass

class AttributeSelector(TerminalSelector):

    def __init__(self, attribute):
        self.attribute = attribute

    def __str__(self):
        return '@' + self.attribute

    def __repr__(self):
        return 'AttributeSelector(%r)' % self.attribute

class DocumentSelector(str):
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
        if selector[:1] == '/':
            selector = selector[1:]
        else:
            raise DocumentSelectorError("Document selector does not start with /")
        if selector[-1:] == '/':
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

    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, str.__repr__(self))

class ElementSelector(list):

    XML_TAG_REGEXP = re.compile('\s*<([^ >/]+)')

    def __init__(self, lst, namespace, namespaces):
        list.__init__(self, lst)
        self.namespace = namespace
        self.namespaces = namespaces

    def _parse_qname(self, qname):
        if qname == '*':
            return qname
        try:
            prefix, name = qname.split(':')
        except ValueError:
            return (self.namespace, qname)
        else:
            return (self.namespaces[prefix], name)

    def replace_default_prefix(self, ns_prefix_mapping):
        steps = []
        for step in self:
            try:
                namespace, name = step.name
            except ValueError:
                steps.append(str(step))
            else:
                steps.append(step.to_string(ns_prefix_mapping))
        return '/' + '/'.join(steps)

    def fix_star(self, element_body):
        """
        >>> elem_selector = parse_node_selector('/watcherinfo/watcher-list/*[@id="8ajksjda7s"]', None, {})[0]
        >>> elem_selector.fix_star('<watcher/>')[-1].name[1]
        'watcher'
        """
        if self and self[-1].name == '*' and self[-1].position is None:
            m = self.XML_TAG_REGEXP.match(element_body)
            if m:
                (name, ) = m.groups()
                result = copy(self)
                result[-1].name = self._parse_qname(name)
                return result
        return self

class NamespaceSelector(TerminalSelector):

    def __str__(self):
        return "namespace::*"

    def __repr__(self):
        return 'NamespaceSelector()'

class NodeSelector(object):

    XMLNS_REGEXP = re.compile("xmlns\((?P<nsdata>.*?)\)")
    XPATH_DEFAULT_PREFIX = 'default'

    def __init__(self, selector, namespace=None):
        self._original_selector = selector
        sections = selector.split('?', 1)

        if len(sections) == 2:
            self.ns_bindings = self._parse_ns_bindings(sections[1])
        else:
            self.ns_bindings = {}

        self.element_selector, self.terminal_selector = parse_node_selector(sections[0], namespace, self.ns_bindings)

    def __str__(self):
        return self._original_selector

    # http://www.w3.org/TR/2003/REC-xptr-xmlns-20030325/
    def _parse_ns_bindings(self, query):
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

    def replace_default_prefix(self, defprefix=None, append_terminal=True):
        if defprefix is None:
            defprefix = self.XPATH_DEFAULT_PREFIX
        namespace2prefix = dict((v, k) for (k, v) in self.ns_bindings.iteritems())
        namespace2prefix[self.element_selector.namespace] = defprefix
        res = self.element_selector.replace_default_prefix(namespace2prefix)
        if append_terminal and self.terminal_selector:
            res += '/' + str(self.terminal_selector)
        return res

    def get_ns_bindings(self, default_ns):
        ns_bindings = self.ns_bindings.copy()
        ns_bindings[self.XPATH_DEFAULT_PREFIX] = default_ns
        return ns_bindings


