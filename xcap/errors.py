
"""XCAP errors module"""

from typing import Optional
from xml.sax.saxutils import quoteattr

from fastapi import HTTPException
from fastapi.responses import Response
from starlette.status import HTTP_404_NOT_FOUND, HTTP_500_INTERNAL_SERVER_ERROR

__all__ = [
    'XCAPError',
    'ResourceNotFound',
    'NotWellFormedError', 'SchemaValidationError', 'NotUTF8Error', 'NotXMLAtrributeValueError',
    'NotXMLFragmentError', 'CannotInsertError', 'CannotDeleteError', 'NoParentError',
    'UniquenessFailureError', 'ConstraintFailureError']


class HTTPError(Exception):
    def __init__(self, response):
        self.response = response

    def __repr__(self) -> str:
        return "<%s %s>" % (self.__class__.__name__, self.response)


class ResourceNotFound(HTTPException):
    def __init__(self, msg: str = "", content_type: Optional[str] = None):
        if content_type is None:
            content_type = "text/plain"

        # Set the status code to 404
        self.status_code = HTTP_404_NOT_FOUND
        self.detail = msg
        self.headers = {"Content-Type": content_type}

    def __str__(self) -> str:
        return self.detail


class NotFound(ResourceNotFound):
    pass


class NoDatabase(ResourceNotFound):
    pass


class DBError(ResourceNotFound):
    def __init__(self, msg: str = "", content_type: Optional[str] = None):
        super().__init__(msg=msg, content_type=content_type)
        self.status_code = HTTP_500_INTERNAL_SERVER_ERROR


class XMLResponse(Response):
    media_type = "application/xcap-error+xml"

    def __init__(self, content: str, status_code: int = 200):
        super().__init__(content=content, status_code=status_code)


class XCAPError(Exception):
    status_code = 409
    namespace = "urn:ietf:params:xml:ns:xcap-error"
    tag = "undefined"
    phrase = ''

    def __init__(self, phrase=None, comment=''):
        if phrase is not None:
            self.phrase = phrase
        if comment:
            self.comment = '<!--\n' + str(comment).replace('-->', '--&gt;') + '\n-->'
        else:
            self.comment = ''
        self.response = XMLResponse(status_code=self.status_code, content=self.build_xml_output())

    def build_xml_output(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
<xcap-error xmlns="%s">%s</xcap-error>""" % (self.namespace, self.format_my_tag())

    def format_my_body(self) -> str:
        return ''

    def format_my_phrase(self) -> str:
        if self.phrase:
            return ' phrase=%s' % quoteattr(self.phrase)
        else:
            return ''

    def format_my_tag(self) -> str:
        phrase_attr = self.format_my_phrase()
        body = self.format_my_body()
        if body or self.comment:
            return '<%s%s>%s%s</%s>' % (self.tag, phrase_attr, self.comment, body, self.tag)
        else:
            return '<%s%s/>' % (self.tag, phrase_attr)

    def __str__(self) -> str:
        return self.format_my_tag()


class SchemaValidationError(XCAPError):
    tag = "schema-validation-error"


class NotXMLFragmentError(XCAPError):
    tag = "not-xml-frag"


class CannotInsertError(XCAPError):
    tag = "cannot-insert"


class CannotDeleteError(XCAPError):
    tag = "cannot-delete"


class NotXMLAtrributeValueError(XCAPError):
    tag = "not-xml-att-value"


class NotWellFormedError(XCAPError):
    tag = "not-well-formed"


class ConstraintFailureError(XCAPError):
    tag = "constraint-failure"


class NotUTF8Error(XCAPError):
    tag = "not-utf-8"


class NoParentError(XCAPError):
    tag = "no-parent"

    def __init__(self, phrase='', ancestor='', comment=''):
        self.ancestor = ancestor
        XCAPError.__init__(self, phrase, comment)

    def format_my_body(self):
        if self.ancestor:
            return "<ancestor>%s</ancestor>" % self.ancestor
        else:
            return ""


class UniquenessFailureError(XCAPError):
    tag = "uniqueness-failure"

    def __init__(self, **kwargs):
        self.exists = kwargs.pop('exists')
        XCAPError.__init__(self, **kwargs)

    def format_my_body(self):
        return "<exists field=%s/>" % quoteattr(self.exists)
