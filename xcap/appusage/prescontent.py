
# Copyright (C) 2007-2010 AG-Projects.
#

from cStringIO import StringIO
from lxml import etree
from xcap import errors
from xcap.appusage import ApplicationUsage


class PresContentApplication(ApplicationUsage):
    id = "org.openmobilealliance.pres-content"
    default_ns = "urn:oma:xml:prs:pres-content"
    mime_type = "application/vnd.oma.pres-content+xml"

    icon_mime_types = ('image/jpeg', 'image/gif', 'image/png')
    icon_encoding = 'base64'
    icon_max_size = 300*1024

    def _validate_icon(self, document):
        mime_type = None
        encoding = None
        data = None
        xml = StringIO(document)
        try:
            tree = etree.parse(xml)
            root = tree.getroot()
            ns = root.nsmap[None]
            for element in root:
                if element.tag == "{%s}mime-type" % ns:
                    mime_type = element.text.lower()
                if element.tag == "{%s}encoding" % ns:
                    encoding = element.text.lower()
                if element.tag == "{%s}data" % ns:
                    data = element.text
        except etree.ParseError:
            raise errors.NotWellFormedError()
        else:
            if mime_type not in self.icon_mime_types:
                raise errors.ConstraintFailureError(phrase="Unsupported MIME type. Allowed MIME types: %s" % ','.join(self.icon_mime_types))
            if encoding != self.icon_encoding:
                raise errors.ConstraintFailureError(phrase="Unsupported encoding. Allowed enconding: %s" % self.icon_encoding)
            if data is None:
                raise errors.ConstraintFailureError(phrase="No icon data was provided")
            if len(data) > self.icon_max_size:
                raise errors.ConstraintFailureError(phrase="Size limit exceeded, maximum allowed size is %d bytes" % self.icon_max_size)

    def put_document(self, uri, document, check_etag):
        if uri.doc_selector.document_path.startswith('oma_status-icon'):
            self._validate_icon(document)
        return self.storage.put_document(uri, document, check_etag)

