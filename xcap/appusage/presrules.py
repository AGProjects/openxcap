
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


class PresenceRulesApplication(ApplicationUsage):
    id = "pres-rules"
    oma_id = "org.openmobilealliance.pres-rules"
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
        common_policy_namespace = 'urn:ietf:params:xml:ns:common-policy'
        oma_namespace = 'urn:oma:xml:xdm:common-policy'

        actions_tag = '{%s}actions' % common_policy_namespace
        conditions_tag = '{%s}conditions' % common_policy_namespace
        identity_tag = '{%s}identity' % common_policy_namespace
        rule_tag = '{%s}rule' % common_policy_namespace
        transformations_tag = '{%s}transformations' % common_policy_namespace

        sub_handling_tag = '{%s}sub-handling' % self.default_ns

        oma_anonymous_request_tag = '{%s}anonymous-request' % oma_namespace
        oma_entry_tag = '{%s}entry' % oma_namespace
        oma_external_list_tag = '{%s}external-list' % oma_namespace
        oma_other_identity_tag = '{%s}other-identity' % oma_namespace

        try:
            xml = StringIO(document)
            tree = etree.parse(xml)
            root = tree.getroot()

            if oma_namespace in root.nsmap.values():
                # Condition constraints
                for element in root.iter(conditions_tag):
                    if any([len(element.findall(item)) > 1 for item in (identity_tag, oma_external_list_tag, oma_other_identity_tag, oma_anonymous_request_tag)]):
                        raise errors.ConstraintFailureError(phrase="Complex rules are not allowed")
                # Transformations constraints
                for rule in root.iter(rule_tag):
                    actions = rule.find(actions_tag)
                    if actions is not None:
                        sub_handling = actions.find(sub_handling_tag)
                        if sub_handling is not None and sub_handling.text != 'allow' and rule.find(transformations_tag) is not None:
                            raise errors.ConstraintFailureError(phrase="transformations element not allowed")
                # External list constraints
                if not ServerConfig.allow_external_references:
                    for element in root.iter(oma_external_list_tag):
                        for entry in element.iter(oma_entry_tag):
                            self._check_external_list(entry.attrib.get('anc', None), node_uri)
        except etree.ParseError:
            raise errors.NotWellFormedError()

    def put_document(self, uri, document, check_etag):
        self.validate_document(document)
        self._validate_rules(document, uri)
        return self.storage.put_document(uri, document, check_etag)


