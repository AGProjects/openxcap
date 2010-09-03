
# Copyright (C) 2007-2010 AG-Projects.
#

from application.configuration import ConfigSection, ConfigSetting
from cStringIO import StringIO
from lxml import etree
from urllib import unquote
from urlparse import urlparse

import xcap
from xcap import errors
from xcap.appusage import ApplicationUsage
from xcap.datatypes import XCAPRootURI
from xcap.uri import XCAPUri
from xcap.xpath import DocumentSelectorError, NodeParsingError


class AuthenticationConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Authentication'

    default_realm = ConfigSetting(type=str, value=None)

class ServerConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Server'

    allow_external_references = False
    root = ConfigSetting(type=XCAPRootURI, value=None)

def parseExternalListURI(node_uri, default_realm):
    from xcap.appusage import namespaces
    xcap_root = None
    for uri in ServerConfig.root.uris:
        if node_uri.startswith(uri):
            xcap_root = uri
            break
    if xcap_root is None:
        raise errors.ConstraintFailureError("XCAP root not found for URI: %s" % node_uri)
    resource_selector = node_uri[len(xcap_root):]
    if not resource_selector or resource_selector == '/':
        raise errors.ConstraintFailureError("Resource selector missing")
    try:
        uri = XCAPUri(xcap_root, resource_selector, namespaces)
    except (DocumentSelectorError, NodeParsingError), e:
        raise errors.ConstraintFailureError(phrase=str(e))
    else:
        if uri.user.domain is None:
            uri.user.domain = default_realm
        return uri

def get_xpath(elem):
    """Return XPATH expression to obtain elem in the document.

    This could be done better, of course, not using stars, but the real tags.
    But that would be much more complicated and I'm not sure if such effort is justified"""
    res = ''
    while elem is not None:
        parent = elem.getparent()
        if parent is None:
            res = '/*' + res
        else:
            res = '/*[%s]' % parent.index(elem) + res
        elem = parent
    return res

def attribute_not_unique(elem, attr):
    raise errors.UniquenessFailureError(exists = get_xpath(elem) + '/@' + attr)


class ResourceListsApplication(ApplicationUsage):
    # RFC 4826
    id = "resource-lists"
    default_ns = "urn:ietf:params:xml:ns:resource-lists"
    mime_type= "application/resource-lists+xml"
    schema_file = 'resource-lists.xsd'

    @classmethod
    def check_list(cls, element, node_uri):
        from xcap.authentication import parseNodeURI
        entry_tag = "{%s}entry" % cls.default_ns
        entry_ref_tag = "{%s}entry-ref" % cls.default_ns
        external_tag ="{%s}external" % cls.default_ns
        list_tag = "{%s}list" % cls.default_ns

        anchor_attrs = set()
        name_attrs = set()
        ref_attrs = set()
        uri_attrs = set()

        for child in element.getchildren():
            if child.tag == list_tag:
                name = child.get("name")
                if name in name_attrs:
                    attribute_not_unique(child, 'name')
                else:
                    name_attrs.add(name)
                cls.check_list(child, node_uri)
            elif child.tag == entry_tag:
                uri = child.get("uri")
                if uri in uri_attrs:
                    attribute_not_unique(child, 'uri')
                else:
                    uri_attrs.add(uri)
            elif child.tag == entry_ref_tag:
                ref = child.get("ref")
                if ref in ref_attrs:
                    attribute_not_unique(child, 'ref')
                else:
                    try:
                        ref = unquote(ref)
                        ref_uri = parseNodeURI("%s/%s" % (node_uri.xcap_root, ref), AuthenticationConfig.default_realm)
                        if not ServerConfig.allow_external_references and ref_uri.user != node_uri.user:
                            raise errors.ConstraintFailureError(phrase="Cannot link to another users' list")
                        try:
                            if ref_uri.node_selector.element_selector[-1].name[1] != "entry":
                                raise ValueError
                        except LookupError:
                            raise ValueError
                    except (DocumentSelectorError, NodeParsingError), e:
                        raise errors.ConstraintFailureError(phrase=str(e))
                    except ValueError:
                        raise errors.ConstraintFailureError
                    else:
                        ref_attrs.add(ref)
            elif child.tag == external_tag:
                anchor = child.get("anchor")
                if anchor in anchor_attrs:
                    attribute_not_unique(child, 'anchor')
                else:
                    anchor = unquote(anchor)
                    if not ServerConfig.allow_external_references:
                        external_list_uri = parseExternalListURI(anchor, AuthenticationConfig.default_realm)
                        if external_list_uri.xcap_root != node_uri.xcap_root:
                            raise errors.ConstraintFailureError(phrase="XCAP root in the external list doesn't match PUT requests'")
                        if external_list_uri.user != node_uri.user:
                            raise errors.ConstraintFailureError(phrase="Cannot link to another users' list")
                    else:
                        parsed_url = urlparse(anchor)
                        if parsed_url.scheme not in ('http', 'https'):
                            raise errors.ConstraintFailureError(phrase='Specified anchor is not a valid URL')
                        else:
                            anchor_attrs.add(anchor)

    def put_document(self, uri, document, check_etag):
        self.validate_document(document)
        # Check additional constraints (see section 3.4.5 of RFC 4826)
        xml_doc = etree.parse(StringIO(document))
        self.check_list(xml_doc.getroot(), uri)
        return self.storage.put_document(uri, document, check_etag)

