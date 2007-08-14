# Copyright (C) 2007 AG Projects.
#

"""XCAP resources module"""

from application import log

from twisted.web2 import http, resource, responsecode, stream, server
from twisted.web2.http_headers import ETag, MimeType
from twisted.web2.static import MetaDataMixin

from xcap.applications import getApplicationForURI
from xcap.errors import *


def log_request(request, size):
    pass
    #uri = request.xcap_uri
    
    ##protocol = "HTTP/%s.%s" % request.clientproto
    ##log.msg("%s %s %s" % (request.method, urllib.unquote(request.uri), protocol))
    #user_agent = request.headers.getHeader('user-agent', 'unknown')
    #msg = "%s from %s %s %s (%d bytes). Client: %s" % (uri.user, request.remoteAddr.host,
                                                #request.method, uri, size, user_agent)
    ##log.msg(msg)
    #print msg


class XCAPResource(resource.Resource, resource.LeafResource, MetaDataMixin):
    
    def __init__(self, xcap_uri, application):
        self.xcap_uri = xcap_uri
        self.application = application
        self.e_tag = None

    def checkPreconditions(self, request):
        ## don't let renderHTTP to automatically check preconditions, we'll do this ourselves
        return None
    
    def checkEtag(self, request, etag):
        http.checkPreconditions(request, etag=ETag(etag))

    def setHeaders(self, response):
        ## Don't provide additional resource information to error responses,
        ## this is already done by the responses in the errors module
        if response.code < 400:
            for (header, value) in (
                ("etag", self.etag()),
                ("content-type", self.contentType())
            ):
                if value is not None:
                    response.headers.setHeader(header, value)
        return response

    def onError(self, f):
        ## If we get an HTTPError, return its attached response
        f.trap(http.HTTPError)
        return f.value.response

    def sendResponse(self, response):
        if response.etag:
            self.e_tag = ETag(response.etag)
        response = http.Response(response.code, stream=response.data)
        return self.setHeaders(response)

    def http_POST(self, request):
        return self.http_PUT(request)

    def etag(self):
        return self.e_tag or None


class XCAPDocument(XCAPResource):

    def http_GET(self, request):
        d = self.application.get_document(self.xcap_uri, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d

    def http_PUT(self, request):
        application = self.application
        document = request.attachment
        d = application.put_document(self.xcap_uri, document, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d

    def http_DELETE(self, request):
        d = self.application.delete_document(self.xcap_uri, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d        

    def contentType(self):
        return MimeType.fromString(self.application.mime_type)


class XCAPElement(XCAPResource):

    content_type = MimeType.fromString("application/xcap-el+xml")

    def http_GET(self, request):
        d = self.application.get_element(self.xcap_uri, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d

    def http_DELETE(self, request):
        d = self.application.delete_element(self.xcap_uri, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d

    def http_PUT(self, request):
        content_type = request.headers.getHeader('content-type')
        if not content_type or content_type != self.content_type:
            raise http.HTTPError(responsecode.UNSUPPORTED_MEDIA_TYPE)
        element = request.attachment
        d = self.application.put_element(self.xcap_uri, element, lambda e: self.checkEtag(request, e))        
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d

    def contentType(self):
        return self.content_type

class XCAPAttribute(XCAPResource):

    content_type = MimeType.fromString("application/xcap-att+xml")

    def contentType(self):
        return self.content_type

    def http_GET(self, request):
        d = self.application.get_attribute(self.xcap_uri, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d

    def http_DELETE(self, request):
        d = self.application.delete_attribute(self.xcap_uri, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d

    def http_PUT(self, request):
        content_type = request.headers.getHeader('content-type')
        if not content_type or content_type != self.content_type:
            raise http.HTTPError(responsecode.UNSUPPORTED_MEDIA_TYPE)
        attribute = request.attachment
        d = self.application.put_attribute(self.xcap_uri, attribute, lambda e: self.checkEtag(request, e))
        d.addCallback(self.sendResponse)
        d.addErrback(self.onError)
        return d
