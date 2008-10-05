# Copyright (C) 2007 AG Projects.
#

"""XCAP errors module"""

from xml.sax.saxutils import quoteattr
from twisted.web2 import http_headers
from twisted.web2.http import Response, HTTPError

__all__ = [
    'XCAPError',
    'ResourceNotFound',
    'NotWellFormedError', 'SchemaValidationError', 'NotUTF8Error', 'NotXMLAtrributeValueError',
    'NotXMLFragmentError', 'CannotInsertError', 'CannotDeleteError', 'NoParentError',
    'UniquenessFailureError', 'ConstraintFailureError']

class ResourceNotFound(HTTPError):
    def __init__(self, msg=""):
        self.msg = msg
        HTTPError.__init__(self, Response(404, stream=msg))

    def __str__(self):
        return self.msg


class XCAPError(HTTPError):

    code = 409
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
        self.response = ErrorResponse(self.code, self.build_xml_output())
        HTTPError.__init__(self, self.response)

    def build_xml_output(self):
        return """<?xml version="1.0" encoding="UTF-8"?>
<xcap-error xmlns="%s">%s</xcap-error>""" % (self.namespace, self.format_my_tag())

    def format_my_body(self):
        return ''

    def format_my_phrase(self):
        if self.phrase:
            return ' phrase=%s' % quoteattr(self.phrase)
        else:
            return ''

    def format_my_tag(self):
        phrase_attr = self.format_my_phrase()
        body = self.format_my_body()
        if body or self.comment:
            return '<%s%s>%s%s</%s>' % (self.tag, phrase_attr, self.comment, body, self.tag)
        else:
            return '<%s%s/>' % (self.tag, phrase_attr)

    def __str__(self):
        try:
            return self.format_my_tag()
        except:
            return ''


class ErrorResponse(Response):
    """
    A L{Response} object which simply contains a status code and a description of
    what happened.
    """

    def __init__(self, code, output):
        """
        @param code: a response code in L{responsecode.RESPONSES}.
        @param output: the body to be attached to the response
        """

        output = output.encode("utf-8")
        mime_params = {"charset": "utf-8"}

        Response.__init__(self, code=code, stream=output)

        ## Its MIME type, registered by this specification, is "application/xcap-error+xml".
        self.headers.setHeader("content-type", http_headers.MimeType("application", "xcap-error+xml", mime_params))

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

class UniquenessFailureError(XCAPError): # TODO
    tag = "uniqueness-failure"

    #<xs:element name="uniqueness-failure"
     #substitutionGroup="error-element">
     #<xs:annotation>
      #<xs:documentation>This indicates that the
   #requested operation would result in a document that did not meet a
   #uniqueness constraint defined by the application usage.
      #</xs:documentation>
     #</xs:annotation>
     #<xs:complexType>
      #<xs:sequence>
       #<xs:element name="exists" maxOccurs="unbounded">
        #<xs:annotation>
         #<xs:documentation>For each URI,
   #element or attribute specified by the client which is not unique,
   #one of these is present.</xs:documentation>
        #</xs:annotation>
        #<xs:complexType>
         #<xs:sequence minOccurs="0">
          #<xs:element name="alt-value" type="xs:string"
           #maxOccurs="unbounded">
           #<xs:annotation>
            #<xs:documentation>An optional set of alternate values can be
   #provided.</xs:documentation>
           #</xs:annotation>
          #</xs:element>
         #</xs:sequence>
         #<xs:attribute name="field" type="xs:string" use="required"/>
        #</xs:complexType>
       #</xs:element>
      #</xs:sequence>
      #<xs:attribute name="description" type="xs:string" use="optional"/>
     #</xs:complexType>
    #</xs:element>


   #<?xml version="1.0" encoding="UTF-8"?>
   #<xcap-error xmlns="urn:ietf:params:xml:ns:xcap-error">
    #<uniqueness-failure>
     #<exists field="rls-services/service/@uri">
       #<alt-value>sip:mybuddies@example.com</alt-value>
     #</exists>
    #</uniqueness-failure>
   #</xcap-error>
