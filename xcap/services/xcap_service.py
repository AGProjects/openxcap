import time
from datetime import datetime
from http import HTTPStatus
from typing import Any, Optional, Union

# services.py
from fastapi import HTTPException, Request, Response
from fastapi.responses import HTMLResponse

from xcap.errors import HTTPError
from xcap.http_utils import ETag, parse_datetime, parse_list_header
from xcap.uri import XCAPUri
from xcap.xpath import AttributeSelector, NamespaceSelector


class StatusResponse(HTMLResponse):
    def __init__(self, status_code: int, description: str, title: Optional[str] = None, **kwargs):
        if not title:
            title = HTTPStatus(status_code).phrase

        content = f"<html><head><title>{title}</title></head><body><h1>{title}</h1><p>{description}</body></html>"
        super().__init__(status_code=status_code, content=content, **kwargs)


def NotModifiedResponse(oldResponse: Optional[Response] = None) -> Response:
    if oldResponse is not None:
        # headers=http_headers.Headers()
        headers = {}
        for header in (
            # Required from sec 10.3.5:
            'date', 'etag', 'content-location', 'expires',
            'cache-control', 'vary',
            # Others:
            'server', 'proxy-authenticate', 'www-authenticate', 'warning'
        ):
            value = oldResponse.headers.get(header)
            if value is not None:
                headers[header] = value
    else:
        headers = None
    return Response(status_code=HTTPStatus.NOT_MODIFIED.value, headers=headers)


# Base class for XCAP resources handling common functionality
class XCAPResource:
    def __init__(self, xcap_uri: XCAPUri, application: Any):
        self.xcap_uri = xcap_uri
        self.application = application
        self.e_tag = None

    def checkPreconditions(self, request: Request, response: Optional[Response] = None, entityExists: bool = True,
                           etag: Union[ETag, list, None] = None, lastModified: Optional[datetime] = None) -> None:
        """Check to see if this request passes the conditional checks specified
        by the client. May raise an HTTPError with result codes L{NOT_MODIFIED}
        or L{PRECONDITION_FAILED}, as appropriate.

        This function is called automatically as an output filter for GET and
        HEAD requests. With GET/HEAD, it is not important for the precondition
        check to occur before doing the action, as the method is non-destructive.

        However, if you are implementing other request methods, like PUT
        for your resource, you will need to call this after determining
        the etag and last-modified time of the existing resource but
        before actually doing the requested action. In that case, 

        This examines the appropriate request headers for conditionals,
        (If-Modified-Since, If-Unmodified-Since, If-Match, If-None-Match,
        or If-Range), compares with the etag and last and
        and then sets the response code as necessary.

        @param response: This should be provided for GET/HEAD methods. If
                 it is specified, the etag and lastModified arguments will
                 be retrieved automatically from the response headers and
                 shouldn't be separately specified. Not providing the
                 response with a GET request may cause the emitted
                 "Not Modified" responses to be non-conformant.

        @param entityExists: Set to False if the entity in question doesn't
                 yet exist. Necessary for PUT support with 'If-None-Match: *'.

        @param etag: The etag of the resource to check against, or None.

        @param lastModified: The last modified date of the resource to check
                  against, or None.

        @raise: HTTPError: Raised when the preconditions fail, in order to
                 abort processing and emit an error page.

        """
        if response:
            assert etag is None and lastModified is None
            # if the code is some sort of error code, don't do anything
            if not ((response.status_code >= 200 and response.status_code <= 299)
                    or response.status_code == HTTPStatus.PRECONDITION_FAILED.value):
                return
            etag_header = response.headers.get("etag")
            etag = parse_list_header(etag_header)
            lastModified_header = response.headers.get("last-modified")
            if lastModified:
                lastModified = parse_datetime(lastModified_header)

        def matchETag(tags, allowWeak):
            if entityExists and '*' in tags:
                return True
            if etag is None:
                return False
            return ((allowWeak or not etag.weak) and
                    ([etagmatch for etagmatch in tags if etag.match(etagmatch, strongCompare=not allowWeak)]))

        # First check if-match/if-unmodified-since
        # If either one fails, we return PRECONDITION_FAILED
        match_header = request.headers.get("if-match")
        if match_header:
            match = parse_list_header(match_header)
            if not matchETag(match, False):
                raise HTTPError(StatusResponse(HTTPStatus.PRECONDITION_FAILED.value, "Requested resource does not have a matching ETag."))

        unmod_since_header = request.headers.get("if-unmodified-since")
        if unmod_since_header:
            unmod_since = parse_datetime(unmod_since_header)
            if not lastModified or unmod_since and lastModified > unmod_since:
                raise HTTPError(StatusResponse(HTTPStatus.PRECONDITION_FAILED.value, "Requested resource has changed."))

        # Now check if-none-match/if-modified-since.
        # This bit is tricky, because of the requirements when both IMS and INM
        # are present. In that case, you can't return a failure code
        # unless *both* checks think it failed.
        # Also, if the INM check succeeds, ignore IMS, because INM is treated
        # as more reliable.

        # I hope I got the logic right here...the RFC is quite poorly written
        # in this area. Someone might want to verify the testcase against
        # RFC wording.

        # If IMS header is later than current time, ignore it.
        notModified = None
        ims_header = request.headers.get('if-modified-since')
        if ims_header:
            ims = parse_datetime(ims_header)
            if ims is not None and lastModified is not None:
                notModified = (ims.timestamp() < time.time() and lastModified and lastModified.timestamp() <= ims.timestamp())
            else:
                notModified = False
        inm_header = request.headers.get("if-none-match")
        if inm_header:
            inm = parse_list_header(inm_header)
            if request.method in ("HEAD", "GET"):
                # If it's a range request, don't allow a weak ETag, as that
                # would break.
                canBeWeak = not request.headers.get('Range')
                if notModified is not False and matchETag(inm, canBeWeak):
                    raise HTTPError(NotModifiedResponse(response))
            else:
                if notModified is not False and matchETag(inm, False):
                    raise HTTPError(StatusResponse(HTTPStatus.PRECONDITION_FAILED.value, "Requested resource has a matching ETag."))
        else:
            if notModified is True:
                if request.method in ("HEAD", "GET"):
                    raise HTTPError(NotModifiedResponse(response))
                else:
                    # S14.25 doesn't actually say what to do for a failing IMS on
                    # non-GET methods. But Precondition Failed makes sense to me.
                    raise HTTPError(StatusResponse(HTTPStatus.PRECONDITION_FAILED.value, "Requested resource has not changed."))

    def check_etag(self, request: Request, etag: str, exists: bool = True) -> None:
        """
        Check ETag header and validate conditions
        """
        self.checkPreconditions(request, etag=ETag(etag), entityExists=exists)

    @property
    def content_type(self) -> str:
        """
        Return the content type of the resource
        """
        if self.application.mime_type:
            return self.application.mime_type

        return "application/xml"  # or other appropriate mime type

    def set_headers(self, response: Response, etag: Optional[str] = None) -> Response:
        """
        Set headers for the response (e.g., ETag, Content-Type)
        """
        if etag:
            response.headers["ETag"] = f'"{etag}"'
        response.headers["Content-Type"] = self.content_type
        return response

    async def handle_get(self, request: Request) -> Response:
        app_data = await self.get_data(request)
        etag = app_data.etag
        content = app_data.data
        response = Response(content=content, status_code=app_data.code)
        return self.set_headers(response, etag)

    async def handle_update(self, request: Request) -> Response:
        app_data = await self.update_data(request)
        etag = app_data.etag
        content = app_data.data
        response = Response(content=content, status_code=app_data.code, background=app_data.background)
        return self.set_headers(response, etag)

    async def handle_delete(self, request: Request) -> Response:
        app_data = await self.delete_data(request)
        etag = app_data.etag
        content = app_data.data
        response = Response(content=content, status_code=app_data.code, background=app_data.background)
        return self.set_headers(response, etag)

    async def get_data(self, request: Request) -> Any:
        """
        Override in subclasses to fetch the actual data for the resource
        """
        raise NotImplementedError("Subclasses must implement this method")

    async def update_data(self, request: Request) -> Any:
        """
        Override in subclasses to fetch the actual data for the resource
        """
        raise NotImplementedError("Subclasses must implement this method")

    async def delete_data(self, request: Request) -> Any:
        """
        Override in subclasses to fetch the actual data for the resource
        """
        raise NotImplementedError("Subclasses must implement this method")


# Function to dynamically select the correct XCAP resource handler based on the URI
def get_xcap_resource(xcap_uri: XCAPUri, application: Any) -> XCAPResource:
    """
    This function selects the correct resource handler (Document, Attribute, NamespaceBinding, Element)
    based on the node_selector and terminal_selector in the xcap_uri.
    """
    if not xcap_uri.node_selector:
        return XCAPDocument(xcap_uri, application)

    terminal_selector = xcap_uri.node_selector.terminal_selector

    if isinstance(terminal_selector, AttributeSelector):
        return XCAPAttribute(xcap_uri, application)
    elif isinstance(terminal_selector, NamespaceSelector):
        return XCAPNamespaceBinding(xcap_uri, application)
    else:
        return XCAPElement(xcap_uri, application)


# XCAPDocument resource handling
class XCAPDocument(XCAPResource):
    async def get_data(self, request: Request) -> str:
        document_data = await self.application.get_document(self.xcap_uri, lambda e: self.check_etag(request, e))
        if not document_data:
            raise HTTPException(status_code=404, detail="Document not found")
        return document_data

    async def update_data(self, request: Request) -> str:
        document = await request.body()
        document_data = await self.application.put_document(self.xcap_uri, document, lambda e, exists=True: self.check_etag(request, e, exists))
        if not document_data:
            raise HTTPException(status_code=404, detail="Document not found")
        return document_data

    async def delete_data(self, request: Request) -> str:
        document_data = await self.application.delete_document(self.xcap_uri, lambda e: self.check_etag(request, e))
        if not document_data:
            raise HTTPException(status_code=404, detail="Document not found")
        return document_data


# XCAPElement resource handling
class XCAPElement(XCAPResource):
    content_type = "application/xcap-el+xml"

    async def get_data(self, request: Request) -> str:
        element_data = await self.application.get_element(self.xcap_uri, lambda e: self.check_etag(request, e))
        if not element_data:
            raise HTTPException(status_code=404, detail="Element not found")
        return element_data

    async def update_data(self, request: Request) -> str:
        content_type = request.headers.get('content-type')
        if not content_type or content_type != self.content_type:
            raise HTTPException(status_code=415, detail="")
        element = await request.body()
        element_data = await self.application.put_element(self.xcap_uri, element, lambda e: self.check_etag(request, e))
        return element_data

    async def delete_data(self, request: Request) -> str:
        element_data = await self.application.delete_element(self.xcap_uri, lambda e: self.check_etag(request, e))
        return element_data


# XCAPAttribute resource handling
class XCAPAttribute(XCAPResource):
    content_type = "application/xcap-att+xml"

    async def get_data(self, request: Request) -> str:
        attribute_data = await self.application.get_attribute(self.xcap_uri, lambda e: self.check_etag(request, e))
        if not attribute_data:
            raise HTTPException(status_code=404, detail="Attribute not found")
        return attribute_data

    async def update_data(self, request: Request) -> str:
        content_type = request.headers.get('content-type')
        if not content_type or content_type != self.content_type:
            raise HTTPException(status_code=415, detail="")
        attribute = await request.body()
        attribute_data = await self.application.put_attribute(self.xcap_uri, attribute, lambda e: self.check_etag(request, e))
        return attribute_data

    async def delete_data(self, request: Request) -> str:
        element_data = await self.application.delete_attribute(self.xcap_uri, lambda e: self.check_etag(request, e))
        return element_data


# XCAPNamespaceBinding resource handling
class XCAPNamespaceBinding(XCAPResource):
    content_type = "application/xcap-ns+xml"

    async def get_data(self, request: Request) -> str:
        ns_binding_data = await self.application.get_ns_bindings(self.xcap_uri, lambda e: self.check_etag(request, e))
        if not ns_binding_data:
            raise HTTPException(status_code=404, detail="Namespace Binding not found")
        return ns_binding_data

