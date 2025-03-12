from fastapi import APIRouter, Depends, HTTPException, Request

from xcap.appusage import getApplicationForURI
from xcap.authentication import AuthenticationManager
from xcap.services.xcap_service import get_xcap_resource
from xcap.uri import XCAPUri

router = APIRouter()

auth_manager = AuthenticationManager()

DEFAULT_DOMAIN = "default.com"


def getApplication(xcap_uri: XCAPUri):
    application = getApplicationForURI(xcap_uri)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return application


@router.get("/xcap-root/", status_code=404)
async def handle_root(xcap_uri: XCAPUri = Depends(auth_manager.authenticate_request)):
    pass


@router.get("/xcap-root/{namespace}/{resource_path:path}")
@router.get("/xcap-root@{domain}/{namespace}/{resource_path:path}")
async def read_xcap_data(
    namespace: str,
    resource_path: str,
    request: Request,
    xcap_uri: XCAPUri = Depends(auth_manager.authenticate_request),
    domain: str = DEFAULT_DOMAIN
):
    application = getApplication(xcap_uri)
    xcap_data = get_xcap_resource(xcap_uri, application)
    return await xcap_data.handle_get(request)


@router.post("/xcap-root/{namespace}/{resource_path:path}")
@router.post("/xcap-root@{domain}/{namespace}/{resource_path:path}")
async def post_not_allowed(request: Request):
    raise HTTPException(status_code=405, detail="POST method is not allowed here")


@router.put("/xcap-root/{namespace}/{resource_path:path}")
@router.put("/xcap-root@{domain}/{namespace}/{resource_path:path}")
async def update_xcap_data_route(
    namespace: str,
    resource_path: str,
    request: Request,
    xcap_uri: XCAPUri = Depends(auth_manager.authenticate_request),
    domain: str = DEFAULT_DOMAIN,
):
    application = getApplication(xcap_uri)
    xcap_data = get_xcap_resource(xcap_uri, application)
    return await xcap_data.handle_update(request)


@router.delete("/xcap-root/{namespace}/{resource_path:path}", status_code=204)
@router.delete("/xcap-root@{domain}/{namespace}/{resource_path:path}", status_code=204)
async def delete_xcap_data_route(
    namespace: str,
    resource_path: str,
    request: Request,
    xcap_uri: XCAPUri = Depends(auth_manager.authenticate_request),
    domain: str = DEFAULT_DOMAIN
):
    application = getApplication(xcap_uri)
    xcap_data = get_xcap_resource(xcap_uri, application)
    return await xcap_data.handle_delete(request)

