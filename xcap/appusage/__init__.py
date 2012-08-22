
# Copyright (C) 2007-2010 AG-Projects.
#

"""XCAP application usage module"""

import os
import sys

from cStringIO import StringIO
from lxml import etree

from application.configuration import ConfigSection, ConfigSetting
from application.configuration.datatypes import StringList
from application import log

import xcap
from xcap import errors
from xcap import element
from xcap.interfaces.backend import StatusResponse


class Backend(object):
    """Configuration datatype, used to select a backend module from the configuration file."""
    def __new__(typ, value):
        value = value.lower()
        try:
            return __import__('xcap.interfaces.backend.%s' % value, globals(), locals(), [''])
        except (ImportError, AssertionError), e:
            log.fatal("Cannot load '%s' backend module: %s" % (value, str(e)))
            sys.exit(1)
        except Exception, e:
            log.err()
            sys.exit(1)


class ServerConfig(ConfigSection):
    __cfgfile__ = xcap.__cfgfile__
    __section__ = 'Server'

    backend = ConfigSetting(type=Backend, value=None)
    disabled_applications = ConfigSetting(type=StringList, value=[])
    document_validation = True

if ServerConfig.backend is None:
    log.fatal("OpenXCAP needs a backend to be specified in order to run")
    sys.exit(1)


class ApplicationUsage(object):
    """Base class defining an XCAP application"""
    id = None                ## the Application Unique ID (AUID)
    default_ns = None        ## the default XML namespace
    mime_type = None         ## the MIME type
    schema_file = None       ## filename of the schema for the application

    def __init__(self, storage):
        ## the XML schema that defines valid documents for this application
        if self.schema_file:
            xml_schema_doc = etree.parse(open(os.path.join(os.path.dirname(__file__), 'xml-schemas', self.schema_file), 'r'))
            self.xml_schema = etree.XMLSchema(xml_schema_doc)
        else:
            class EverythingIsValid(object):
                def __call__(self, *args, **kw):
                    return True
                def validate(self, *args, **kw):
                    return True
            self.xml_schema = EverythingIsValid()
        if storage is not None:
            self.storage = storage

    ## Validation

    def _check_UTF8_encoding(self, xml_doc):
        """Check if the document is UTF8 encoded. Raise an NotUTF8Error if it's not."""
        if xml_doc.docinfo.encoding.lower() != 'utf-8':
            raise errors.NotUTF8Error(comment='document encoding is %s' % xml_doc.docinfo.encoding)

    def _check_schema_validation(self, xml_doc):
        """Check if the given XCAP document validates against the application's schema"""
        if not self.xml_schema(xml_doc):
            raise errors.SchemaValidationError(comment=self.xml_schema.error_log)

    def _check_additional_constraints(self, xml_doc):
        """Check additional validations constraints for this XCAP document. Should be
           overriden in subclasses if specified by the application usage, and raise
           a ConstraintFailureError if needed."""

    def validate_document(self, xcap_doc):
        """Check if a document is valid for this application."""
        try:
            xml_doc = etree.parse(StringIO(xcap_doc))
            # XXX do not use TreeBuilder here
        except etree.XMLSyntaxError, ex:
            ex.http_error = errors.NotWellFormedError(comment=str(ex))
            raise
        except Exception, ex:
            ex.http_error = errors.NotWellFormedError()
            raise
        self._check_UTF8_encoding(xml_doc)
        if ServerConfig.document_validation:
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

    def _not_implemented(self, context):
        raise errors.ResourceNotFound("Application %s does not implement %s context" % (self.id, context))

    def get_document(self, uri, check_etag):
        context = uri.doc_selector.context
        if context == 'global':
            return self.get_document_global(uri, check_etag)
        elif context == 'users':
            return self.get_document_local(uri, check_etag)
        else:
            self._not_implemented(context)

    def get_document_global(self, uri, check_etag):
        self._not_implemented('global')

    def get_document_local(self, uri, check_etag):
        return self.storage.get_document(uri, check_etag)

    def put_document(self, uri, document, check_etag):
        self.validate_document(document)
        return self.storage.put_document(uri, document, check_etag)

    def delete_document(self, uri, check_etag):
        return self.storage.delete_document(uri, check_etag)

    ## Element management

    def _cb_put_element(self, response, uri, element_body, check_etag):
        """This is called when the document that relates to the element is retrieved."""
        if response.code == 404:          ### XXX let the storate raise
            raise errors.NoParentError    ### catch error in errback and attach http_error

        fixed_element_selector = uri.node_selector.element_selector.fix_star(element_body)

        try:
            result = element.put(response.data, fixed_element_selector, element_body)
        except element.SelectorError, ex:
            ex.http_error = errors.NoParentError(comment=str(ex))
            raise

        if result is None:
            raise errors.NoParentError

        new_document, created = result
        get_result = element.get(new_document, uri.node_selector.element_selector)

        if get_result != element_body.strip():
            raise errors.CannotInsertError('PUT request failed GET(PUT(x))==x invariant')

        d = self.put_document(uri, new_document, check_etag)

        def set_201_code(response):
            try:
                if response.code==200:
                    response.code = 201
            except AttributeError:
                pass
            return response

        if created:
            d.addCallback(set_201_code)

        return d

    def put_element(self, uri, element_body, check_etag):
        try:
            element.check_xml_fragment(element_body)
        except element.sax.SAXParseException, ex:
            ex.http_error = errors.NotXMLFragmentError(comment=str(ex))
            raise
        except Exception, ex:
            ex.http_error = errors.NotXMLFragmentError()
            raise
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_put_element, callbackArgs=(uri, element_body, check_etag))

    def _cb_get_element(self, response, uri):
        """This is called when the document related to the element is retrieved."""
        if response.code == 404:     ## XXX why not let the storage raise?
            raise errors.ResourceNotFound("The requested document %s was not found on this server" % uri.doc_selector)
        result = element.get(response.data, uri.node_selector.element_selector)
        if not result:
            msg = "The requested element %s was not found in the document %s" % (uri.node_selector, uri.doc_selector)
            raise errors.ResourceNotFound(msg)
        return StatusResponse(200, response.etag, result)

    def get_element(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_get_element, callbackArgs=(uri, ))

    def _cb_delete_element(self, response, uri, check_etag):
        if response.code == 404:
            raise errors.ResourceNotFound("The requested document %s was not found on this server" % uri.doc_selector)
        new_document = element.delete(response.data, uri.node_selector.element_selector)
        if not new_document:
            raise errors.ResourceNotFound
        get_result = element.find(new_document, uri.node_selector.element_selector)
        if get_result:
            raise errors.CannotDeleteError('DELETE request failed GET(DELETE(x))==404 invariant')
        return self.put_document(uri, new_document, check_etag)

    def delete_element(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_delete_element, callbackArgs=(uri, check_etag))

    ## Attribute management
    def _cb_get_attribute(self, response, uri):
        """This is called when the document that relates to the attribute is retrieved."""
        if response.code == 404:
            raise errors.ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        application = getApplicationForURI(uri)
        ns_dict = uri.node_selector.get_ns_bindings(application.default_ns)
        try:
            xpath = uri.node_selector.replace_default_prefix()
            attribute = xml_doc.xpath(xpath, namespaces = ns_dict)
        except Exception, ex:
            ex.http_error = errors.ResourceNotFound()
            raise
        if not attribute:
            raise errors.ResourceNotFound
        elif len(attribute) != 1:
            raise errors.ResourceNotFound('XPATH expression is ambiguous')
        # TODO
        # The server MUST NOT add namespace bindings representing namespaces
        # used by the element or its children, but declared in ancestor elements
        return StatusResponse(200, response.etag, attribute[0])

    def get_attribute(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_get_attribute, callbackArgs=(uri, ))

    def _cb_delete_attribute(self, response, uri, check_etag):
        if response.code == 404:
            raise errors.ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        application = getApplicationForURI(uri)
        ns_dict = uri.node_selector.get_ns_bindings(application.default_ns)
        try:
            elem = xml_doc.xpath(uri.node_selector.replace_default_prefix(append_terminal=False),namespaces=ns_dict)
        except Exception, ex:
            ex.http_error = errors.ResourceNotFound()
            raise
        if not elem:
            raise errors.ResourceNotFound
        if len(elem) != 1:
            raise errors.ResourceNotFound('XPATH expression is ambiguous')
        elem = elem[0]
        attribute = uri.node_selector.terminal_selector.attribute
        if elem.get(attribute):  ## check if the attribute exists XXX use KeyError instead
            del elem.attrib[attribute]
        else:
            raise errors.ResourceNotFound
        new_document = etree.tostring(xml_doc, encoding='UTF-8', xml_declaration=True)
        return self.put_document(uri, new_document, check_etag)

    def delete_attribute(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_delete_attribute, callbackArgs=(uri, check_etag))

    def _cb_put_attribute(self, response, uri, attribute, check_etag):
        """This is called when the document that relates to the element is retrieved."""
        if response.code == 404:
            raise errors.NoParentError
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        application = getApplicationForURI(uri)
        ns_dict = uri.node_selector.get_ns_bindings(application.default_ns)
        try:
            elem = xml_doc.xpath(uri.node_selector.replace_default_prefix(append_terminal=False),namespaces=ns_dict)
        except Exception, ex:
            ex.http_error = errors.NoParentError()
            raise
        if not elem:
            raise errors.NoParentError
        if len(elem) != 1:
            raise errors.NoParentError('XPATH expression is ambiguous')
        elem = elem[0]
        attr_name = uri.node_selector.terminal_selector.attribute
        elem.set(attr_name, attribute)
        new_document = etree.tostring(xml_doc, encoding='UTF-8', xml_declaration=True)
        return self.put_document(uri, new_document, check_etag)

    def put_attribute(self, uri, attribute, check_etag):
        ## TODO verify if the attribute is valid
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_put_attribute, callbackArgs=(uri, attribute, check_etag))

    ## Namespace Bindings
    def _cb_get_ns_bindings(self, response, uri):
        """This is called when the document that relates to the element is retrieved."""
        if response.code == 404:
            raise errors.ResourceNotFound
        document = response.data
        xml_doc = etree.parse(StringIO(document))
        application = getApplicationForURI(uri)
        ns_dict = uri.node_selector.get_ns_bindings(application.default_ns)
        try:
            elem = xml_doc.xpath(uri.node_selector.replace_default_prefix(append_terminal=False),namespaces=ns_dict)
        except Exception, ex:
            ex.http_error =  errors.ResourceNotFound()
            raise
        if not elem:
            raise errors.ResourceNotFound
        elif len(elem)!=1:
            raise errors.ResourceNotFound('XPATH expression is ambiguous')
        elem = elem[0]
        namespaces = ''
        for prefix, ns in elem.nsmap.items():
            namespaces += ' xmlns%s="%s"' % (prefix and ':%s' % prefix or '', ns)
        result = '<%s %s/>' % (elem.tag, namespaces)
        return StatusResponse(200, response.etag, result)

    def get_ns_bindings(self, uri, check_etag):
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_get_ns_bindings, callbackArgs=(uri, ))


from xcap.appusage.capabilities import XCAPCapabilitiesApplication
from xcap.appusage.dialogrules import DialogRulesApplication
from xcap.appusage.directory import XCAPDirectoryApplication
from xcap.appusage.pidf import PIDFManipulationApplication
from xcap.appusage.prescontent import PresContentApplication
from xcap.appusage.presrules import PresenceRulesApplication
from xcap.appusage.purge import PurgeApplication
from xcap.appusage.resourcelists import ResourceListsApplication
from xcap.appusage.rlsservices import RLSServicesApplication
from xcap.appusage.test import TestApplication
from xcap.appusage.watchers import WatchersApplication

storage = ServerConfig.backend.Storage()

applications = {
                DialogRulesApplication.id:          DialogRulesApplication(storage),
                PIDFManipulationApplication.id:     PIDFManipulationApplication(storage),
                PresContentApplication.id:          PresContentApplication(storage),
                PresenceRulesApplication.id:        PresenceRulesApplication(storage),
                PresenceRulesApplication.oma_id:    PresenceRulesApplication(storage),
                PurgeApplication.id:                PurgeApplication(storage),
                ResourceListsApplication.id:        ResourceListsApplication(storage),
                RLSServicesApplication.id:          RLSServicesApplication(storage),
                TestApplication.id:                 TestApplication(storage),
                WatchersApplication.id:             WatchersApplication(storage),
                XCAPCapabilitiesApplication.id:     XCAPCapabilitiesApplication(),
                XCAPDirectoryApplication.id:        XCAPDirectoryApplication(storage)
                }

# public GET applications (GET is not challenged for auth)
public_get_applications = {}
applications.update(public_get_applications)

for application in ServerConfig.disabled_applications:
    applications.pop(application, None)

namespaces = dict((k, v.default_ns) for (k, v) in applications.items())

def getApplicationForURI(xcap_uri):
    return applications.get(xcap_uri.application_id, None)


__all__ = ['applications', 'namespaces', 'public_get_applications', 'getApplicationForURI', 'ApplicationUsage', 'Backend']


