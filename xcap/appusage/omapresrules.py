
# Copyright (C) 2007-2010 AG-Projects.
#

from application.configuration import ConfigSection, ConfigSetting
from cStringIO import StringIO
from lxml import etree

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

class OMAPresenceRulesApplication(ApplicationUsage):
    id = "org.openmobilealliance.pres-rules"
    default_ns = "urn:ietf:params:xml:ns:pres-rules"
    mime_type = "application/auth-policy+xml"
    schema_file = 'presence-rules.xsd'

    def _check_external_list(self, external_list, node_uri):
        if not external_list:
            return
        external_list_uri = parseExternalListURI(external_list, AuthenticationConfig.default_realm)
        if external_list_uri.xcap_root != node_uri.xcap_root:
            raise errors.ConstraintFailureError(phrase="XCAP root in the external list doesn't match PUT requests'")
        if external_list_uri.user != node_uri.user:
            raise errors.ConstraintFailureError(phrase="Cannot link to another users' list")

    def _validate_rules(self, document, node_uri):
        try:
            xml = StringIO(document)
            tree = etree.parse(xml)
            root = tree.getroot()
            oma_namespace = 'urn:oma:xml:xdm:common-policy'
            for element in root.iter("{%s}external-list" % oma_namespace):
                for entry in element.iter("{%s}entry" % oma_namespace):
                    self._check_external_list(entry.attrib.get('anc', None), node_uri)
        except etree.ParseError:
            raise errors.NotWellFormedError()

    def put_document(self, uri, document, check_etag):
        self.validate_document(document)
        self._validate_rules(document, uri)
        return self.storage.put_document(uri, document, check_etag)

