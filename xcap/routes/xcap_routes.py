from fastapi import APIRouter, Depends, HTTPException, Request

from xcap.authentication import AuthData, AuthenticationManager
from xcap.services.xcap_service import get_xcap_resource
from xcap.uri import XCAPUri

router = APIRouter()

auth_manager = AuthenticationManager()

DEFAULT_DOMAIN = "default.com"


@router.get("/xcap-root/", status_code=404)
async def handle_root(xcap_uri: XCAPUri = Depends(auth_manager.authenticate_xcap_request)):
    pass


@router.get("/xcap-root/{namespace}/{resource_path:path}")
@router.get("/xcap-root@{domain}/{namespace}/{resource_path:path}")
async def read_xcap_data(
    namespace: str,
    resource_path: str,
    request: Request,
    auth_data: AuthData = Depends(auth_manager.authenticate_xcap_request),
    domain: str = DEFAULT_DOMAIN
):
    xcap_data = get_xcap_resource(auth_data.xcap_uri, auth_data.application)
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
    auth_data: AuthData = Depends(auth_manager.authenticate_xcap_request),
    domain: str = DEFAULT_DOMAIN,
):
    xcap_data = get_xcap_resource(auth_data.xcap_uri, auth_data.application)
    return await xcap_data.handle_update(request)


@router.delete("/xcap-root/{namespace}/{resource_path:path}", status_code=204)
@router.delete("/xcap-root@{domain}/{namespace}/{resource_path:path}", status_code=204)
async def delete_xcap_data_route(
    namespace: str,
    resource_path: str,
    request: Request,
    auth_data: AuthData = Depends(auth_manager.authenticate_xcap_request),
    domain: str = DEFAULT_DOMAIN
):
    xcap_data = get_xcap_resource(auth_data.xcap_uri, auth_data.application)
    return await xcap_data.handle_delete(request)

