
# Copyright (C) 2007-2010 AG-Projects.
#

from lxml import etree
from xcap import errors
from xcap.appusage import ApplicationUsage
from xcap.dbutil import make_etag
from xcap.interfaces.backend import StatusResponse

class WatchersApplication(ApplicationUsage):
    id = "org.openxcap.watchers"
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
        raise errors.ResourceNotFound("This application does not support PUT method")


