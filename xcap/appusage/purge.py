# Copyright (C) 2011 AG-Projects.
#

from xcap import errors
from xcap.appusage import ApplicationUsage
from xcap.interfaces.backend import StatusResponse

class PurgeApplication(ApplicationUsage):
    id = "org.openxcap.purge"
    default_ns = "http://openxcap.org/ns/purge"

    def _purge_cb(self, result, uri):
        return StatusResponse(200)

    def get_document_local(self, uri, check_etag):
        d = self.storage.delete_documents(uri)
        d.addCallback(self._purge_cb, uri)
        return d

    def put_document(self, uri, document, check_etag):
        raise errors.ResourceNotFound("This application does not support PUT method")

    def delete_document(self, uri, document, check_etag):
        raise errors.ResourceNotFound("This application does not support DELETE method")

