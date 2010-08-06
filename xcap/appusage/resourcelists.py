
# Copyright (C) 2007-2010 AG-Projects.
#

from application.configuration import ConfigSection, ConfigSetting
from cStringIO import StringIO
from lxml import etree

import xcap
from xcap import errors
from xcap.appusage import ApplicationUsage
from xcap.xpath import DocumentSelectorError, NodeParsingError


class AuthenticationConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Authentication'

    default_realm = ConfigSetting(type=str, value=None)

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
        external_tag ="{%s}tag" % cls.default_ns
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
                        ref_uri = parseNodeURI("%s/%s" % (node_uri.xcap_root, ref), AuthenticationConfig.default_realm)
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
                    # TODO check if it's a HTTP URL, else raise ConstraintFailure
                    anchor_attrs.add(anchor)

    def put_document(self, uri, document, check_etag):
        self.validate_document(document)
        # Check additional constraints (see section 3.4.5 of RFC 4826)
        xml_doc = etree.parse(StringIO(document))
        self.check_list(xml_doc.getroot(), uri)
        return self.storage.put_document(uri, document, check_etag)

