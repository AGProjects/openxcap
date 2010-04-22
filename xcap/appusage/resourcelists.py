
# Copyright (C) 2007-2010 AG-Projects.
#

from xcap import errors
from xcap.appusage import ApplicationUsage

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
    ## RFC 4826
    id = "resource-lists"
    default_ns = "urn:ietf:params:xml:ns:resource-lists"
    mime_type= "application/resource-lists+xml"
    schema_file = 'resource-lists.xsd'

    @classmethod
    def check_list(cls, elem, list_tag):
        """Check additional constraints (see section 3.4.5 of RFC 4826).

        elem is xml Element that containts <list>s
        list_tag is provided as argument since its namespace changes from resource-lists
        to rls-services namespace
        """
        entry_tag = "{%s}entry" % cls.default_ns
        entry_ref_tag = "{%s}entry-ref" % cls.default_ns
        external_tag ="{%s}tag" % cls.default_ns
        name_attrs = set()
        uri_attrs = set()
        ref_attrs = set()
        anchor_attrs = set()
        for child in elem.getchildren():
            if child.tag == list_tag:
                name = child.get("name")
                if name in name_attrs:
                    attribute_not_unique(child, 'name')
                else:
                    name_attrs.add(name)
                cls.check_list(child, list_tag)
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
                    # TODO check if it's a relative URI, else raise ConstraintFailure
                    ref_attrs.add(ref)
            elif child.tag == external_tag:
                anchor = child.get("anchor")
                if anchor in anchor_attrs:
                    attribute_not_unique(child, 'anchor')
                else:
                    # TODO check if it's a HTTP URL, else raise ConstraintFailure
                    anchor_attrs.add(anchor)

    def _check_additional_constraints(self, xml_doc):
        """Check additional constraints (see section 3.4.5 of RFC 4826)."""
        self.check_list(xml_doc.getroot(), "{%s}list" % self.default_ns)



