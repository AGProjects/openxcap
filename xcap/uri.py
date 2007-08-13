# Copyright (C) 2007 AG Projects.
#

"""XCAP URI module"""

import re
import urlparse

from application.configuration import readSettings, ConfigSection, getSection
from application import log
from application.debug.timing import timer

#from xcap.authentication import XCAPUser
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

class DocumentSelector(object):
    """DocumentSelector has the following attributes: application_id, context, user_id
       and document."""
    
    def __init__(self, selector):
        segments  = selector.split('/')
        if not segments[0]:
            segments.pop(0)
        if not segments[-1]:
            segments.pop()
        if len(segments) < 2:
            raise ResourceNotFound("invalid document selector")
        self.application_id = segments[0]
        self.context = segments[1]     ## either "global" or "users"
        if self.context not in ("users", "global"):
            raise ResourceNotFound("the doc selector context must be 'users' or 'global'")
        self.user_id = None
        if self.context == "users":
            self.user_id = segments[2]
            segments = segments[3:]
        else:
            segments = segments[2:]
        if not segments:
            raise ResourceNotFound("missing documents path")
        self.document = segments[-1]


class NodeSelector(object):
    
    xmlns_regexp = re.compile(r'^xmlns\((?P<p>[_a-z]+)=(?P<ns>[0-9a-z:_\.\-]+)\)$', re.IGNORECASE|re.UNICODE)
    
    def __init__(self, selector):
        _sections = selector.split('?', 1)
        segs = _sections[0].strip('/').split('/')  ## the Node Selector segments
        segs = [s.find(':') == -1 and 'default:' + s or s for s in segs]
        self.target_selector = '/' + '/'.join(segs[:-1])
        self.target_node = segs[-1]
        self.selector = '%s/%s' % (self.target_selector, self.target_node)
        #print 'target selector: ', self.target_selector
        #print 'target node: ', self.target_node
        #print 'node selector: ', self.selector
        self.ns_bindings = {'default': None}
        if len(_sections) == 2:
            expr = _sections[1].split()  ## the list of xpointer expressions
            for e in expr:
                m = re.match(self.xmlns_regexp, e)
                if m:
                    self.ns_bindings[m.group('p')] = m.group('ns')
                
    ## http://www.w3.org/TR/2003/REC-xptr-xmlns-20030325/
    def get_ns_bindings(self, default_ns):
        self.ns_bindings['default'] = default_ns
        return self.ns_bindings


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
        self.doc_selector = DocumentSelector(_split[0])  ## the Document Selector
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

def test():
    uri = "http://xcap.example.com/test/users/sip:joe@example.com/index/~~/foo/a:bar/b:baz?xmlns(a=urn:test:namespace1-uri)xmlns(b=urn:test:namespace1-uri)"
    t = timer(count)    
    for i in xrange(count):
        XCAPUri(uri)
    t.end(rate=True, msg="XCAP URI parses")    

if __name__ == "__main__":
    uri = "http://xcap.example.com/test/users/sip:joe@example.com/index/~~/foo/a:bar/b:baz?xmlns(a=urn:test:namespace1-uri)xmlns(b=urn:test:namespace1-uri)"
    
    #uri = XCAPUri(uri)
    #print 'XCAP root: ', uri.xcap_root
    #doc_selector = uri.doc_selector
    #print 'Document Selector'
    #print '\tApplication ID: ', doc_selector.application_id
    #print '\tContext: ', doc_selector.context
    #print '\tUser ID: ', doc_selector.user_id
    #print '\tDocument: ', doc_selector.document
    #node_selector = uri.node_selector

    #node_selector = NodeSelector('/foo/a:bar/b:baz?xmlns(a=urn:test:namespace1-uri) xmlns(b=urn:test:namespace1-uri) ')
    #node_selector = NodeSelector('/foo/a:bar/b:baz?xmlns(a=urn:test:namespace1-uri) xmlns(b=urn:test:namespace2-uri)')
    #node_selector = NodeSelector('/d:foo/a:bar/b:baz?xmlns(a=urn:test:namespace1-uri) xmlns(b=urn:test:namespace2-uri) xmlns(d=urn:test:default-namespace)')
    node_selector = NodeSelector('watcherinfo/watcher-list1/watcher[@id="8ajksjda7s"]')
    
    print 'Node Selector'
    print '\tSelector: ', node_selector.selector
    print '\tNS bindings: ', node_selector.get_ns_bindings('urn:test:default-namespace')

    from lxml import etree
    from StringIO import StringIO
    
    
    #document = """<?xml version="1.0"?>
   #<foo xmlns="urn:test:default-namespace">
     #<ns1:bar xmlns:ns1="urn:test:namespace1-uri"
              #xmlns="urn:test:namespace1-uri">
       #<baz/>
       #<ns2:baz xmlns:ns2="urn:test:namespace2-uri"/>
     #</ns1:bar>
     #<ns3:hi xmlns:ns3="urn:test:namespace3-uri">
       #<there/>
     #</ns3:hi>
   #</foo>"""

    document =     '''<?xml version="1.0"?>
   <watcherinfo xmlns="urn:ietf:params:xml:ns:watcherinfo"
                version="0" state="full">
     <watcher-list resource="sip:professor@example.net"
                   package="presence">
       <watcher status="active"
                id="8ajksjda7s"
                duration-subscribed="509"
                event="approved">sip:userA@example.net</watcher>
       <watcher status="pending"
                id="hh8juja87s997-ass7"
                display-name="Mr. Subscriber"
                event="subscribe">sip:userB@example.org</watcher>
     </watcher-list>
   </watcherinfo>'''   
   
    xml_doc = etree.parse(StringIO(document))
    #ns_dict = node_selector.get_ns_bindings('urn:test:default-namespace')
    ns_dict = node_selector.get_ns_bindings('urn:ietf:params:xml:ns:watcherinfo')
    
    ## active watchers
    print node_selector.selector
    print ns_dict
    
    result = xml_doc.xpath(node_selector.selector, ns_dict)
    print result
    #print dir(result[0])
    
    print etree.tostring(result[0])
    print result[0]
    # test()

