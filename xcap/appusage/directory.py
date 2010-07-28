
# Copyright (C) 2007-2010 AG-Projects.
#

from lxml import etree
from twisted.internet import defer
from xcap import errors
from xcap.appusage import ApplicationUsage
from xcap.interfaces.backend import StatusResponse

class XCAPDirectoryApplication(ApplicationUsage):
    id = "org.openmobilealliance.xcap-directory"
    default_ns = "urn:oma:xml:xdm:xcap-directory"
    mime_type= "application/vnd.oma.xcap-directory+xml"
    schema_file = "xcap-directory.xsd"

    def _docs_to_xml(self, docs, uri):
        sip_uri = "sip:%s@%s" % (uri.user.username, uri.user.domain)
        root = etree.Element("xcap-directory", nsmap={None: self.default_ns})
        if docs:
            for k, v in docs.iteritems():
                folder = etree.SubElement(root, "folder", attrib={'auid': k})
                for item in v:
                    # We may have more than one document for the same application
                    entry_uri = "%s/%s/users/%s/%s" % (uri.xcap_root, k, sip_uri, item[0])
                    entry = etree.SubElement(folder, "entry")
                    entry.set("uri", entry_uri)
                    entry.set("etag", item[1])
        doc = etree.tostring(root, encoding="UTF-8", pretty_print=True, xml_declaration=True)
        #self.validate_document(doc)
        return defer.succeed(StatusResponse(200, etag=None, data=doc))

    def get_document_local(self, uri, check_etag):
        docs_def = self.storage.get_documents_list(uri)
        docs_def.addCallback(self._docs_to_xml, uri)
        return docs_def

    def put_document(self, uri, document, check_etag):
        raise errors.ResourceNotFound("This application does not support PUT method")


