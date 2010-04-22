
# Copyright (C) 2007-2010 AG-Projects.
#

import base64
import Image

from cStringIO import StringIO
from lxml import etree
from xcap import errors
from xcap.appusage import ApplicationUsage
from xcap.interfaces.backend import StatusResponse

class IconApplication(ApplicationUsage):
    id = "oma_status-icon"
    default_ns = "urn:oma:xml:prs:pres-content"
    mime_type = "application/vnd.oma.pres-content+xml"

    def _validate_icon(self, document):
        allowed_mime_types = ['jpg', 'gif', 'png']
        allowed_encodings = ['base64']
        allowed_max_size = 256
        try:
            xml = StringIO(document)
            tree = etree.parse(xml)
            root = tree.getroot()
            icon = None
            ns = root.nsmap[None]
            for element in root:
                if element.tag == "{%s}mime-type" % ns:
                    if not (len(element.text.split("/")) == 2 and element.text.split("/")[1].lower() in allowed_mime_types):
                        raise errors.ConstraintFailureError(phrase="Unsupported MIME type. Allowed MIME type(s) %s" % allowed_mime_types)
                if element.tag == "{%s}encoding" % ns:
                    if not element.text.lower() in allowed_encodings:
                        raise errors.ConstraintFailureError(phrase="Unsupported encoding. Allowed enconding(s) %s" % allowed_encodings)
                if element.tag == "{%s}data" % ns:
                    try:
                        icon = base64.decodestring(element.text)
                    except:
                        raise errors.ConstraintFailureError(phrase="Unsupported encoding. Allowed enconding(s) %s" % allowed_encodings)
        except etree.ParseError:
            raise errors.NotWellFormedError()
        else:
            try:
                img = Image.open(StringIO(icon))
            except (IOError, TypeError):
                raise errors.ConstraintFailureError(phrase="Can't detect an image in the payload.")
            else:
                if not (img.size[0] == img.size[1] and img.size[0] <= allowed_max_size):
                    raise errors.ConstraintFailureError(phrase="Image size error. Maximum allowed size is 256 pixels aspect ratio 1:1")
                if img.format.lower() not in allowed_mime_types:
                    raise errors.ConstraintFailureError(phrase="Unsupported MIME type. Allowed MIME type(s) %s" % allowed_mime_types)

    def put_document(self, uri, document, check_etag):
        self._validate_icon(document)
        return self.storage.put_document(uri, document, check_etag)

    def _extract_and_return_icon(self, status):
        if status.code != 200:
            return status
        try:
            xml = StringIO(status.data)
            tree = etree.parse(xml)
            root = tree.getroot()
            ns = root.nsmap[None]
            icon = None
        except etree.ParseError:
            return StatusResponse(500)
        else:
            for element in root:
                if element.tag == "{%s}data" % ns:
                    try:
                        icon = base64.decodestring(element.text)
                    except:
                        return StatusResponse(500)
                    else:
                        break
            if icon:
                return StatusResponse(200, etag=status.etag, data=icon)
            else:
                return StatusResponse(500)

    def get_document_local(self, uri, check_etag):
        doc_def = self.storage.get_document(uri, check_etag)
        doc_def.addCallback(self._extract_and_return_icon)
        return doc_def


