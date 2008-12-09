"""XCAP application usage module"""

import os
import sys

from cStringIO import StringIO
from lxml import etree

from application.configuration.datatypes import StringList
from application import log

from twisted.internet import defer

from xcap.config import ConfigFile, ConfigSection
from xcap import errors
from xcap.interfaces.backend import StatusResponse
from xcap import element
from xcap.dbutil import make_etag

supported_applications = ('xcap-caps', 'pres-rules', 'org.openmobilealliance.pres-rules',
                          'resource-lists', 'rls-services', 'pidf-manipulation', 'watchers')

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
        value = value.lower()
        try:
            return __import__('xcap.interfaces.backend.%s' % value, globals(), locals(), [''])
        except ImportError, e:
            log.fatal("Cannot load '%s' backend module: %s" % (value, str(e)))
            sys.exit(1)
        except Exception, e:
            log.err()
            sys.exit(1)

class ServerConfig(ConfigSection):
    _datatypes = {'applications': EnabledApplications, 'backend': Backend}
    applications = EnabledApplications("all")
    backend = Backend('Database')
    document_validation = True

configuration = ConfigFile()
configuration.read_settings('Server', ServerConfig)

schemas_directory = os.path.join(os.path.dirname(__file__), "../", "xml-schemas")

class ApplicationUsage(object):
    """Base class defining an XCAP application"""
    id = None                ## the Application Unique ID (AUID)
    default_ns = None        ## the default XML namespace
    mime_type = None         ## the MIME type
    schema_file = None       ## filename of the schema for the application
    
    def __init__(self, storage):
        ## the XML schema that defines valid documents for this application
        if self.schema_file:
            xml_schema_doc = etree.parse(open(os.path.join(schemas_directory, self.schema_file), 'r'))
            self.xml_schema = etree.XMLSchema(xml_schema_doc)
        else:
            class EverythingIsValid:
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
        """This is called when the document that relates to the element is retreived."""
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
        """This is called when the document that relates to the attribute is retreived."""
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
        """This is called when the document that relates to the element is retreived."""
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
        ## TODO verifica daca atributul e valid
        d = self.get_document(uri, check_etag)
        return d.addCallbacks(self._cb_put_attribute, callbackArgs=(uri, attribute, check_etag))

    ## Namespace Bindings
    
    def _cb_get_ns_bindings(self, response, uri):
        """This is called when the document that relates to the element is retreived."""
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


class PresenceRulesApplication(ApplicationUsage):
    ## draft-ietf-simple-presence-rules-09
    id = "pres-rules"
    default_ns = "urn:ietf:params:xml:ns:pres-rules"
    mime_type = "application/auth-policy+xml"
    schema_file = 'common-policy.xsd'


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


class RLSServicesApplication(ApplicationUsage):
    ## RFC 4826
    id = "rls-services"
    default_ns = "urn:ietf:params:xml:ns:rls-services"
    mime_type= "application/rls-services+xml"
    schema_file = 'rls-services.xsd'

    def _check_additional_constraints(self, xml_doc):
        """Check additional constraints (see section 3.4.5 of RFC 4826)."""
        ResourceListsApplication.check_list(xml_doc.getroot(), "{%s}list" % self.default_ns)


class PIDFManipulationApplication(ApplicationUsage):
    ## RFC 4827
    id = "pidf-manipulation"
    default_ns = "urn:ietf:params:xml:ns:pidf"
    mime_type= "application/pidf+xml"
    schema_file = 'pidf.xsd'


class XCAPCapabilitiesApplication(ApplicationUsage):
    ## RFC 4825
    id = "xcap-caps"
    default_ns = "urn:ietf:params:xml:ns:xcap-caps"
    mime_type= "application/xcap-caps+xml"

    def __init__(self):
        pass

    def _get_document(self):
        if hasattr(self, 'doc'):
            return self.doc, self.etag
        auids = ""
        extensions = ""
        namespaces = ""
        for (id, app) in applications.items():
            auids += "<auid>%s</auid>\n" % id
            namespaces += "<namespace>%s</namespace>\n" % app.default_ns
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
        self.etag = make_etag('xcap-caps', self.doc)
        return self.doc, self.etag

    def get_document_global(self, uri, check_etag):
        doc, etag = self._get_document()
        return defer.succeed(StatusResponse(200, etag=etag, data=doc))

    def get_document_local(self, uri, check_etag):
        self._not_implemented('users')


class WatchersApplication(ResourceListsApplication): # QQQ why does it inherit from ResourceLists?
    id = "watchers"
    default_ns = "http://openxcap.org/ns/watchers"
    mime_type= "application/xml"
    schema_file = 'watchers.xsd' # who needs schema for readonly application?

    def _watchers_to_xml(self, watchers, uri, check_etag):
        root = etree.Element("watchers", nsmap={None: self.default_ns})
        for watcher in watchers:
            watcher_elem = etree.SubElement(root, "watcher")
            for name, value in watcher.iteritems():
                etree.SubElement(watcher_elem, name).text = value
        doc = etree.tostring(root, encoding="utf-8", pretty_print=True, xml_declaration=True)
        #self.validate_document(doc)
        etag = make_etag(uri, doc)
        check_etag(etag)
        return StatusResponse(200, data=doc, etag=etag)

    def get_document_local(self, uri, check_etag):
        watchers_def = self.storage.get_watchers(uri)
        watchers_def.addCallback(self._watchers_to_xml, uri, check_etag)
        return watchers_def

    def put_document(self, uri, document, check_etag):
        raise errors.ResourceNotFound("This application is read-only") # TODO: test and add better error

theStorage = ServerConfig.backend.Storage()

class TestApplication(ApplicationUsage):
    "Application for tests described in Section 8.2.3. Creation of RFC 4825"
    id = "test-app"
    default_ns = 'test-app'
    mime_type= "application/test-app+xml"
    schema_file = None

applications = {'xcap-caps': XCAPCapabilitiesApplication(),
                'pres-rules': PresenceRulesApplication(theStorage),
                'org.openmobilealliance.pres-rules': PresenceRulesApplication(theStorage),
                'resource-lists': ResourceListsApplication(theStorage),
                'pidf-manipulation': PIDFManipulationApplication(theStorage),
                'watchers': WatchersApplication(theStorage),
                'rls-services': RLSServicesApplication(theStorage),
                'test-app': TestApplication(theStorage)}

namespaces = dict((k, v.default_ns) for (k, v) in applications.items())

def getApplicationForURI(xcap_uri):
    return applications.get(xcap_uri.application_id, None)
