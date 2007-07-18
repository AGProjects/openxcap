# Copyright (C) 2007 AG Projects.
#

"""XCAP application module"""

import os
import time

from StringIO import StringIO
from lxml import etree

from application.configuration import readSettings, ConfigSection
from application.process import process

from xcap.storage import DatabaseStorage
from xcap.errors import *


#class ServerConfig(ConfigSection):

class StorageConfig(ConfigSection):
    backend = 'database'
    db_uri = 'mysql://user:pass@db/openser'

## We use this to overwrite some of the settings above on a local basis if needed
readSettings('Storage', StorageConfig)


class XCAPApplication(object):
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

    def _check_schema_validation(self, xcap_doc):
        """Check if the given XCAP document validates against the application's schema"""
        try:
            xml_doc = etree.parse(StringIO(xcap_doc))
        except: ## not a well formed XML document
            raise NotWellFormedError
        if not self.xml_schema.validate(xml_doc):
            raise SchemaValidationError("The document doesn't comply to the XML schema")

    def _check_additional_constraints(self, xcap_doc):
        """Check additional validations constraints for this XCAP document. Should be 
           overriden in subclasses if specified by the application usage, and raise
           a ConstraintFailureError if needed."""
        pass

    def _check_UTF8_encoding(self, xcap_doc):
        """Check if the document is UTF8 encoded. Raise an NotUTF8Error if not."""
        raise NotUTF8Error()

    def validate_document(self, xcap_doc):
        """Check if a document is valid for this application."""
        # self._check_UTF8_encoding(self, xcap_doc)
        #self._check_schema_validation(xcap_doc)
        self._check_additional_constraints(xcap_doc)

    #def validate_element(self, element):
    #    """Check if an element is valid."""
    
    ## Authorization policy
    
    def is_authorized(self, xcap_user, xcap_uri):
        """Default authorization policy. Authorizes an XCAPUser for an XCAPUri.
           Return True if the user is authorized, False otherwise."""
        if xcap_user and xcap_user == xcap_uri.user:
            return True
        return False

    def compute_etag(self, xcap_uri):
        return str(time.time())

    ## Document management

    def get_document(self, uri, check_etag):
        return self.storage.get_document(uri, check_etag)

    def put_document(self, uri, document, check_etag):
        self.validate_document(document)
        return self.storage.put_document(uri, document, check_etag)
    
    def delete_document(self, uri, check_etag):
        return self.storage.delete_document(uri, check_etag)
    
    ## Element management
    
    def _create_element(self, parent, elem):
        pass
    
    def _modify_element(self, parent, target, elem):
        pass
    
    def _cb_put_element(self, document, uri, xml_elem):
        """This is called when the document that relates to the element is retreived."""
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_ns_bindings(application.default_ns)
        try:
            parent = xml_doc.xpath(node_selector.target_selector, ns_dict)
        except:
            raise Exception # TODO ce exceptie intoarcem daca selectorul nu e valid ?
        if not parent or len(parent) > 1:
            raise NoParentError
        parent = parent[0]
        target = parent.xpath(node_selector.target_node, ns_dict)
        if target:
            self._modify_element(parent, target[0], xml_elem)
        else:
            self._create_element(parent, xml_elem)
    
    def _eb_put_element(self, f):
        """This is called if the document that relates to the element does not exist."""
        f.trap(ResourceNotFound)
        raise NoParentError # TODO
    
    def put_element(self, uri, element):
        try:
            xml_elem = etree.parse(StringIO(element))
            # verifica daca are un singur element, daca nu arunca aceeasi exceptie TODO
        except:
            raise NotXMLFragmentError
        d = self.get_document(self, uri)
        return d.addCallbacks(self._cb_put_element, self._eb_put_element,
                              callbackArgs=(uri, xml_elem))
    
    def _cb_get_element(self, document, uri):
        """This is called when the document that relates to the element is retreived."""
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_ns_bindings(application.default_ns)
        try:
            elem = xml_doc.xpath(node_selector.selector, ns_dict)
        except:
            raise ResourceNotFound
        if not elem:
            raise ResourceNotFound
        # TODO
        # The server MUST NOT add namespace bindings representing namespaces 
        # used by the element or its children, but declared in ancestor elements
        return etree.tostring(elem[0])
    
    def _eb_get_element(self, f):
        """This is called if the document that relates to the element does not exist."""
        f.trap(ResourceNotFound)
        raise ResourceNotFound
    
    def get_element(self, uri):
        d = self.get_document(uri)
        return d.addCallbacks(self._cb_get_element, self._eb_get_element,
                              callbackArgs=(uri, ))

    def _cb_delete_element(self, document, uri):
        xml_doc = etree.parse(StringIO(document))
        node_selector = uri.node_selector
        application = getApplicationForURI(uri)
        ns_dict = node_selector.get_ns_bindings(application.default_ns)
        try:
            elem = xml_doc.xpath(node_selector.selector, ns_dict)
        except:
            raise ResourceNotFound
        if not elem or len(elem) > 1:
            raise ResourceNotFound
        
        # TODO
        # The server MUST NOT add namespace bindings representing namespaces 
        # used by the element or its children, but declared in ancestor elements
        return self.put_document(uri, document)

    def _eb_delete_element(self, f):
        """This is called if the document that relates to the element does not exist."""
        f.trap(ResourceNotFound)
        raise ResourceNotFound
    
    def delete_element(self, uri):
        d = self.get_document(uri)
        return d.addCallbacks(self._cb_delete_element, self._eb_delete_element,
                              callbackArgs=(uri, ))

    def get_etag(self, uri):
        return self.storage.get_etag(uri)


class PresenceRulesApplication(XCAPApplication):
    ## draft-ietf-simple-presence-rules-09
    id = "pres-rules"
    default_ns = "urn:ietf:params:xml:ns:pres-rules"
    mime_type = "application/auth-policy+xml"


class ResourceListsApplication(XCAPApplication):
    ## RFC 4826
    id = "resource-lists"
    default_ns = "urn:ietf:params:xml:ns:resource-lists"
    mime_type= "application/resource-lists+xml"


class RLSServicesApplication(XCAPApplication):
    ## RFC 4826
    id = "rls-services"
    default_ns = "urn:ietf:params:xml:ns:rls-services"
    mime_type= "application/rls-services+xml"


class PIDFManipulationApplication(XCAPApplication):
    ## RFC 4827
    id = "pidf-manipulation"
    default_ns = "urn:ietf:params:xml:ns:pidf"
    mime_type= "application/pidf+xml"


class XCAPCapabilitiesApplication(XCAPApplication):
    ## RFC 4825
    id = "xcap-caps"
    default_ns = "urn:ietf:params:xml:ns:xcap-caps"
    mime_type= "application/xcap-caps+xml"


schemas_directory = os.path.join(process._local_config_directory, 'xml-schemas')
#try:
storage_backend = __import__('xcap.interfaces.storage.%s' % StorageConfig.backend, globals(), locals(), [''])
#except ImportError:
#    raise RuntimeError("Couldn't find the '%s' storage module" % StorageConfig.backend)
Storage = storage_backend.Storage


applications = {'pres-rules':     PresenceRulesApplication(open(os.path.join(schemas_directory, 'presence-rules.xsd'), 'r').read(), Storage()),
                'org.openmobilealliance.pres-rules': PresenceRulesApplication(open(os.path.join(schemas_directory, 'presence-rules.xsd'), 'r').read(), Storage()),
                'resource-lists': ResourceListsApplication(open(os.path.join(schemas_directory, 'resource-lists.xsd'), 'r').read(), Storage()),
                'pidf-manipulation': PIDFManipulationApplication(open(os.path.join(schemas_directory, 'resource-lists.xsd'), 'r').read(), Storage())}


def getApplicationForURI(xcap_uri):
    return applications.get(xcap_uri.application_id, None)
