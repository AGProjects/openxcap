# Copyright (C) 2007 AG Projects.
#

"""XCAP URI module"""

import re
import urlparse

from application.configuration import readSettings, ConfigSection, getSection
from application import log

import xcap
from xcap.errors import *


class XCAPRootURIs(tuple):
    """Configuration data type. A tuple of defined XCAP Root URIs is extracted from
       the configuration file."""
    def __new__(typ):
        uris = [value for name, value in getSection("Server") or [] if name == "root"]
        for uri in uris:
            scheme, host, path, params, query, fragment = urlparse.urlparse(uri)
            if not scheme or not host or scheme not in ("http", "https"):
                log.warn("XCAP Root URI not valid: %s" % uri)
                uris.remove(uri)
        if not uris:
            raise ResourceNotFound("At least one XCAP Root URI must be defined")
        return tuple(uris)

root_uris = XCAPRootURIs()

class ServerConfig(ConfigSection):
    _dataTypes = {'root_uris': XCAPRootURIs}
    root_uris = ()

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('Server', ServerConfig)

print 'Supported Root URIs: %s' % ','.join(root_uris)


class TerminalSelector(str): pass
class AttributeSelector(TerminalSelector): pass
class NamespaceSelector(TerminalSelector): pass
class ExtensionSelector(TerminalSelector): pass

class NodeSelector(str):

    XMLNS_REGEXP = re.compile("xmlns\((?P<nsdata>.*?)\)")
    XPATH_DEFAULT_NS = "default"

    def __init__(self, selector):
        _sections = selector.split('?', 1)
        segs = _sections[0].strip('/').split('/')  ## the Node Selector segments
        if len(segs) > 1:
            terminal = segs.pop()
            if terminal.startswith('@'):
                self.terminal_selector = AttributeSelector(terminal)
            elif terminal == 'namespace::*':
                self.terminal_selector = NamespaceSelector(terminal)
            else:
                if terminal.find(':') == -1:
                    terminal = '%s:%s' % (self.XPATH_DEFAULT_NS, terminal)
                self.terminal_selector = ExtensionSelector(terminal)
        else:
            self.terminal_selector = None
        segs = [s.find(':') == -1 and '%s:%s' % (self.XPATH_DEFAULT_NS, s) or s for s in segs]
        self.element_selector = '/' + '/'.join(segs)
        if len(_sections) == 2: ## a query component is present
            self.ns_bindings = self._parse_query(_sections[1])
        else:
            self.ns_bindings = {}
        str.__init__(self, '%s/%s' % (self.element_selector, self.terminal_selector))

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

    def get_xpath_ns_bindings(self, default_ns):
        ns_bindings = self.ns_bindings.copy()
        ns_bindings[self.XPATH_DEFAULT_NS] = default_ns
        return ns_bindings


class DocumentSelector(str):
    """Constructs a DocumentSelector containing the application_id, context, user_id
       and document from the given selector string."""

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
            raise ValueError("the Document Selector context must be 'users' or 'global'")
        self.user_id = None
        if self.context == "users":
            self.user_id = segments[2]
            segments = segments[3:]
        else:
            segments = segments[2:]
        if not segments:
            raise ValueError("invalid Document Selector: missing document's path")
        self.document = segments[-1]
        str.__init__(self, selector)


class XCAPUri(object):
    """An XCAP URI containing the XCAP root, document selector and node selector."""

    node_selector_separator = "~~"

    def __init__(self, xcap_root, resource_selector, default_realm='example.com'):
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
        if len(_split) == 2:                             ## the Node Selector
            self.node_selector = NodeSelector(_split[1]) 
        else:
            self.node_selector = None
        self.user = xcap.authentication.XCAPUser(self.doc_selector.user_id)
        if not self.user.domain:
            self.user.domain = realm
        self.application_id = self.doc_selector.application_id

    def __str__(self):
        return self.xcap_root + self.resource_selector


def parseNodeURI(node_uri, default_realm='example.com'):
    """Parses the given Node URI, containing the XCAP root, document selector,
       and node selector, and returns an XCAPUri instance if succesful."""
    xcap_root = None
    for uri in root_uris:
        if node_uri.startswith(uri):
            xcap_root = uri
            break
    if xcap_root is None:
        raise ResourceNotFound("XCAP root not found for uri: %s" % node_uri)
    resource_selector = node_uri[len(xcap_root):]
    return XCAPUri(xcap_root, resource_selector, default_realm)
