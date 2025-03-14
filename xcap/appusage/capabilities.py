
from lxml import etree
#from twisted.internet import defer
from xcap import errors
from xcap.appusage import ApplicationUsage
from xcap.dbutil import make_etag
from xcap.backend import StatusResponse


class XCAPCapabilitiesApplication(ApplicationUsage):
    ## RFC 4825
    id = "xcap-caps"
    default_ns = "urn:ietf:params:xml:ns:xcap-caps"
    mime_type = "application/xcap-caps+xml"

    def __init__(self):
        pass

    async def _get_document(self):
        if hasattr(self, 'doc'):
            return self.doc, self.etag
        root = etree.Element("xcap-caps", nsmap={None: self.default_ns})
        auids = etree.SubElement(root, "auids")
        extensions = etree.SubElement(root, "extensions")
        namespaces = etree.SubElement(root, "namespaces")

        from xcap.appusage import applications
        for (id, app) in list(applications.items()):
            etree.SubElement(auids, "auid").text = id
            etree.SubElement(namespaces, "namespace").text = app.default_ns
        self.doc = etree.tostring(root, encoding="UTF-8", pretty_print=True, xml_declaration=True)
        self.etag = make_etag('xcap-caps', self.doc)
        return self.doc, self.etag

    async def get_document_global(self, uri, check_etag):
        doc, etag = await self._get_document()
        return StatusResponse(code=200, etag=etag, data=doc)

    def get_document_local(self, uri, check_etag):
        self._not_implemented('users')

    def put_document(self, uri, document, check_etag):
        raise errors.ResourceNotFound("This application does not support PUT method")

