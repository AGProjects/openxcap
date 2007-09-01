# Copyright (C) 2007 AG Projects.
#

"""XCAP application usage module"""

import os

from StringIO import StringIO
from lxml import etree

from application.configuration import readSettings, ConfigSection
from application.configuration.datatypes import StringList
from application.process import process
from application import log

from twisted.internet import defer
from twisted.python import failure

from xcap.errors import *
from xcap.interfaces.backend import StatusResponse

supported_applications = ('xcap-caps', 'pres-rules', 'org.openmobilealliance.pres-rules',
                          'resource-lists', 'pidf-manipulation')

class EnabledApplications(StringList):
    def __new__(typ, value):
        apps = StringList.__new__(typ, value)
        if len(apps) == 1 and apps[0] == "all":
            return supported_applications
        for app in apps:
            if app not in supported_applications:
                log.warn("ignoring unknown application : %s" % app)
                apps.remove(app)
        return apps

class Backend(object):
    """Configuration datatype, used to select a backend module from the configuration file."""
    def __new__(typ, value):
        try:
            return __import__('xcap.interfaces.backend.%s' % value.lower(), globals(), locals(), [''])
        except ImportError, e:
            raise ValueError("Couldn't find the '%s' backend module: %s" % (value.lower(), str(e)))

class ServerConfig(ConfigSection):
    _dataTypes = {'applications': EnabledApplications, 'backend': Backend}
    applications = EnabledApplications("all")
    backend = Backend('Database')

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('Server', ServerConfig)


class ApplicationUsage(object):
    """Base class defining an XCAP application"""
    id = None                ## the Application Unique ID (AUID)
    default_ns = None        ## the default XML namespace
    mime_type = None         ## the MIME type
    
    def __init__(self, xml_schema_buff, storage):
        ## the XML schema that defines valid documents for this application
        xml_schema_doc = etree.parse(StringIO(xml_schema_buff))
        self.xml_schema = etree.XMLSchema(xml_schema_doc)
        self.storage = storage

    ## Validation

    def _check_UTF8_encoding(self, xml_doc):
        """Check if the document is UTF8 encoded. Raise an NotUTF8Error if it's not."""
        if xml_doc.docinfo.encoding != 'UTF-8':
            log.error("The document is not UTF-8 encoded. Encoding is : %s" % xml_doc.docinfo.encoding)
            raise NotUTF8Error()

    def _check_schema_validation(self, xml_doc):
        """Check if the given XCAP document validates against the application's schema"""
        if not self.xml_schema.validate(xml_doc):
            log.error("Failed to validate document against XML schema: %s" % self.xml_schema.error_log)
            raise SchemaValidationError("The document doesn't comply to the XML schema")

    def _check_additional_constraints(self, xml_doc):
        """Check additional validations constraints for this XCAP document. Should be 
           overriden in subclasses if specified by the application usage, and raise
           a ConstraintFailureError if needed."""
        pass

    def validate_document(self, xcap_doc):
        """Check if a document is valid for this application."""
        try:
            xml_doc = etree.parse(StringIO(xcap_doc))
        except: ## not a well formed XML document
            log.error("XML document is not well formed.")
            raise NotWellFormedError
        self._check_UTF8_encoding(xml_doc)
        self._check_schema_validation(xml_doc)
        self._check_additional_constraints(xml_doc)

    ## Authorization policy

    def is_authorized(self, xcap_user, xcap_uri):
        """Default authorization policy. Authorizes an XCAPUser for an XCAPUri.
           Return True if the user is authorized, False otherwise."""
        if xcap_user and xcap_user == xcap_uri.user:
            return True
        return False

    ## Document management

    def get_document(self, uri, check_etag):
        return self.storage.get_document(uri, check_etag)

    def put_document(self, uri, document, check_etag):
        try:
            self.validate_document(document)
        except Exception:
            return defer.fail(failure.Failure())
        return self.storage.put_document(uri, document, check_etag)

    def delete_document(self, uri, check_etag):
        return self.storage.delete_document(uri, check_etag)

    ## Element management

    def _create_element(self, parent, terminal_selector, elem):
        left = target.find('[')
        if left == -1:
            name = target
            position = None
        else:
            name = target[:left]
            right = target.find(']')
            content = target[left+1:right]
            if content[0] != '@':
                position = int(content)
            else:
                position = None
        if position is None: ## there is no positional constraint
            i = 0
            sibling_found = False
            for child in parent:
                if child.tag == name:
                    sibling_found = True
                if child.tag != name and sibling_found:
                    parent.insert(i, elem)
                    break
                i += 1
            if len(parent) == i: ## we've reached the end without inserting the new element
                parent.append(elem)
        else: ## a positional insertion
            wildcard = name == "*"
            i = 0
            j = 1
            for child in parent:
                if position == j:
                    parent.insert(i, elem)
                    break
                if (wildcard and type(child) is etree._Element) or (not wildcard and child.tag == name):
                    j += 1
                i += 1
            if wildcard and position == j:
                parent.insert(i, elem)

    def _replace_element(self, parent, target, elem):
        parent.replace(target, elem)

    def _cb_put_element(self, response, uri, xml_elem, check_etag):
        """This is called when the document that relates to the element is retreived."""
        if response.code == 404:
            raise NoParentError
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_xpath_ns_bindings(application.default_ns)
        try:
            parent = xml_doc.xpath(node_selector.element_selector, ns_dict)
        except:
            raise NoParentError
            #raise Exception # TODO ce exceptie intoarcem daca selectorul nu e valid ?
        if len(parent) != 1:
            raise NoParentError
        parent = parent[0]
        target = parent.xpath(node_selector.terminal_selector, ns_dict)
        if target:
            self._replace_element(parent, target[0], xml_elem)
        else:
            self._create_element(parent, node_selector.terminal_selector, xml_elem)
        new_document = etree.tostring(xml_doc, 'UTF-8', xml_declaration=True)
        return self.put_document(uri, new_document, check_etag)

    def put_element(self, uri, element, check_etag):
        try:
            xml_elem = etree.parse(StringIO(element)).getroot()
            # verifica daca are un singur element, daca nu arunca aceeasi exceptie ? TODO
        except:
            raise NotXMLFragmentError
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_put_element, callbackArgs=(uri, xml_elem, check_etag))

    def _cb_get_element(self, response, uri):
        """This is called when the document that relates to the element is retreived."""
        if response.code == 404:
            raise ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_xpath_ns_bindings(application.default_ns)
        try:
            selector = node_selector.element_selector + '/' + node_selector.terminal_selector
            elem = xml_doc.xpath(selector, ns_dict)
        except:
            raise ResourceNotFound
        if not elem:
            raise ResourceNotFound
        # TODO
        # The server MUST NOT add namespace bindings representing namespaces 
        # used by the element or its children, but declared in ancestor elements
        return StatusResponse(200, response.etag, etree.tostring(elem[0]))

    def get_element(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_get_element, callbackArgs=(uri, ))

    def _cb_delete_element(self, response, uri, check_etag):
        if response.code == 404:
            raise ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))        
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_xpath_ns_bindings(application.default_ns)
        try:
            selector = node_selector.element_selector + '/' + node_selector.terminal_selector
            elem = xml_doc.xpath(selector, ns_dict)
        except:
            raise ResourceNotFound
        if len(elem) != 1:
            raise ResourceNotFound
        elem = elem[0]
        elem.getparent().remove(elem)
        new_document = etree.tostring(xml_doc, 'UTF-8', xml_declaration=True)
        return self.put_document(uri, new_document, check_etag)

    def delete_element(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_delete_element, callbackArgs=(uri, check_etag))

    ## Attribute management
    
    def _cb_get_attribute(self, response, uri):
        """This is called when the document that relates to the attribute is retreived."""
        if response.code == 404:
            raise ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_xpath_ns_bindings(application.default_ns)
        try:
            selector = node_selector.element_selector + '/' + node_selector.terminal_selector
            attribute = xml_doc.xpath(selector, ns_dict)
        except:
            raise ResourceNotFound
        if len(attribute) != 1:
            raise ResourceNotFound
        # TODO
        # The server MUST NOT add namespace bindings representing namespaces 
        # used by the element or its children, but declared in ancestor elements
        return StatusResponse(200, response.etag, attribute[0])

    def get_attribute(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_get_attribute, callbackArgs=(uri, ))

    def _cb_delete_attribute(self, response, uri, check_etag):
        if response.code == 404:
            raise ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))        
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_xpath_ns_bindings(application.default_ns)
        try:
            elem = xml_doc.xpath(node_selector.element_selector, ns_dict)
        except:
            raise ResourceNotFound
        if len(elem) != 1:
            raise ResourceNotFound
        elem = elem[0]
        attribute = node_selector.terminal_selector[1:]
        if elem.get(attribute):  ## check if the attribute exists
            del elem.attrib[attribute]
        else:
            raise ResourceNotFound
        new_document = etree.tostring(xml_doc, 'UTF-8', xml_declaration=True)
        return self.put_document(uri, new_document, check_etag)

    def delete_attribute(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_delete_attribute, callbackArgs=(uri, check_etag))

    def _cb_put_attribute(self, response, uri, attribute, check_etag):
        """This is called when the document that relates to the element is retreived."""
        if response.code == 404:
            raise NoParentError
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_xpath_ns_bindings(application.default_ns)
        try:
            elem = xml_doc.xpath(node_selector.element_selector, ns_dict)
        except:
            raise NoParentError
            #raise Exception # TODO ce exceptie intoarcem daca selectorul nu e valid ?
        if len(elem) != 1:
            raise NoParentError
        elem = elem[0]
        attr_name = node_selector.terminal_selector[1:]
        elem.set(attr_name, attribute)
        new_document = etree.tostring(xml_doc, 'UTF-8', xml_declaration=True)
        return self.put_document(uri, new_document, check_etag)

    def put_attribute(self, uri, attribute, check_etag):
        ## TODO verifica daca atributul e valid
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_put_attribute, callbackArgs=(uri, attribute, check_etag))

    ## Namespace Bindings
    
    def _cb_get_ns_bindings(self, response, uri):
        """This is called when the document that relates to the element is retreived."""
        if response.code == 404:
            raise ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_xpath_ns_bindings(application.default_ns)
        try:
            #selector = node_selector.element_selector + '/' + node_selector.terminal_selector
            selector = node_selector.element_selector
            elem = xml_doc.xpath(selector, ns_dict)
        except:
            raise ResourceNotFound
        if not elem:
            raise ResourceNotFound
        elem = elem[0]
        namespaces = ''
        for prefix, ns in elem.nsmap.items():
            namespaces += ' xmlns%s="%s"' % (prefix and ':%s' % prefix or '', ns)
        result = '<%s %s/>' % (elem.tag, namespaces)
        return StatusResponse(200, response.etag, result)

    def get_ns_bindings(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_get_ns_bindings, callbackArgs=(uri, ))


class PresenceRulesApplication(ApplicationUsage):
    ## draft-ietf-simple-presence-rules-09
    id = "pres-rules"
    default_ns = "urn:ietf:params:xml:ns:pres-rules"
    mime_type = "application/auth-policy+xml"


class ResourceListsApplication(ApplicationUsage):
    ## RFC 4826
    id = "resource-lists"
    default_ns = "urn:ietf:params:xml:ns:resource-lists"
    mime_type= "application/resource-lists+xml"
    
    def _check_additional_constraints(self, xml_doc):
        """Check additional constraints (see section 3.4.5 of RFC 4826)."""
        list_tag = "{%s}list" % self.default_ns
        entry_tag = "{%s}entry" % self.default_ns
        entry_ref_tag = "{%s}entry-ref" % self.default_ns
        external_tag ="{%s}tag" % self.default_ns
        for elem in xml_doc.getiterator():
            name_attrs = set()
            uri_attrs = set()
            ref_attrs = set()
            anchor_attrs = set()
            for child in elem.getchildren():
                if child.tag == list_tag:
                    name = child.get("name")
                    if name in name_attrs:
                        raise UniquenessFailureError()
                    else:
                        name_attrs.add(name)
                elif child.tag == entry_tag:
                    uri = child.get("uri")
                    if uri in uri_attrs:
                        raise UniquenessFailureError()
                    else:
                        uri_attrs.add(uri)
                elif child.tag == entry_ref_tag:
                    ref = child.get("ref")
                    if ref in ref_attrs:
                        raise UniquenessFailureError()
                    else:
                        # TODO check if it's a relative URI, else raise ConstraintFailure
                        ref_attrs.add(ref)
                elif child.tag == external_tag:
                    anchor = child.get("anchor")
                    if anchor in anchor_attrs:
                        raise UniquenessFailureError()
                    else:
                        # TODO check if it's a HTTP URL, else raise ConstraintFailure
                        anchor_attrs.add(anchor)


class RLSServicesApplication(ApplicationUsage):
    ## RFC 4826
    id = "rls-services"
    default_ns = "urn:ietf:params:xml:ns:rls-services"
    mime_type= "application/rls-services+xml"


class PIDFManipulationApplication(ApplicationUsage):
    ## RFC 4827
    id = "pidf-manipulation"
    default_ns = "urn:ietf:params:xml:ns:pidf"
    mime_type= "application/pidf+xml"


class XCAPCapabilitiesApplication(ApplicationUsage):
    ## RFC 4825
    id = "xcap-caps"
    default_ns = "urn:ietf:params:xml:ns:xcap-caps"
    mime_type= "application/xcap-caps+xml"

    def __init__(self):
        pass

    def _get_document(self):
        if hasattr(self, 'doc'):
            return self.doc
        auids = ""
        extensions = ""
        namespaces = ""
        for (id, app) in applications.items():
            auids += "<auid>%s<auid>\n" % id
            namespaces += "<namespace>%s<namespace>\n" % app.default_ns
        self.doc = """<?xml version='1.0' encoding='UTF-8'?>
        <xcap-caps xmlns='urn:ietf:params:xml:ns:xcap-caps'>
            <auids>
            %(auids)s</auids>
            <extensions>
            %(extensions)s</extensions>
            <namespaces>
            %(namespaces)s</namespaces>
        </xcap-caps>""" % {"auids": auids,
                           "extensions": extensions,
                           "namespaces": namespaces}
        return self.doc

    def get_document(self, uri, check_etag):
        return defer.succeed(StatusResponse(200, data=self._get_document()))


schemas_directory = os.path.join(os.path.dirname(globals()["__file__"]), "../", "xml-schemas")
Storage = ServerConfig.backend.Storage

applications = {'xcap-caps':      XCAPCapabilitiesApplication(),
                'pres-rules':     PresenceRulesApplication(open(os.path.join(schemas_directory, 'common-policy.xsd'), 'r').read(), Storage()),
                'org.openmobilealliance.pres-rules': PresenceRulesApplication(open(os.path.join(schemas_directory, 'common-policy.xsd'), 'r').read(), Storage()),
                'resource-lists': ResourceListsApplication(open(os.path.join(schemas_directory, 'resource-lists.xsd'), 'r').read(), Storage()),
                'pidf-manipulation': PIDFManipulationApplication(open(os.path.join(schemas_directory, 'pidf.xsd'), 'r').read(), Storage())}


def getApplicationForURI(xcap_uri):
    return applications.get(xcap_uri.application_id, None)
