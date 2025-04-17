from typing import Any, Dict, List, Union

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str


def error_response(description: str, details: Union[str, List[str]]) -> Dict[str, Any]:
    if isinstance(details, list):
        examples = {f"error_{i+1}": {"summary": f"Error {i+1}", "value": {"detail": detail}} for i, detail in enumerate(details)}
        return {
            "description": description,
            "model": ErrorResponse,
            "content": {
                "application/json": {
                    "examples": examples
                }
            },
        }
    return {
        "description": description,
        "model": ErrorResponse,
        "content": {
            "application/json": {
                "example": {"detail": details}
            }
        },
    }


COMMON_ERRORS: Dict[Union[int, str], Dict[str, Any]] = {
    401: error_response("Unauthorized", "Not authenticated"),
    404: error_response("User not found", "User not found"),
    # 403: error_response(403, "Forbidden", "Not enough permissions"),
}


def error_responses(route_type: str) -> Dict[Union[int, str], Dict[str, Any]]:
    name = route_type.capitalize()
    return {
        **COMMON_ERRORS,
        404: error_response(f"{name} not found", f"{name} not found")
    }


ICON_ERRORS: Dict[Union[int, str], Dict[str, Any]] = {
    **COMMON_ERRORS,
    304: {},
}

CONTACT_ADD_ERRORS: Dict[Union[int, str], Dict[str, Any]] = {
    **error_responses("contact"),
    409: error_response("Conflict", "Contact already present"),
}

GROUP_MEMBER_ERRORS: Dict[Union[int, str], Dict[str, Any]] = {
    **COMMON_ERRORS,
    404: error_response("Group or contact not found", ["Group not found", "Contact not found"]),
}

GROUP_MEMBER_ADD_ERRORS: Dict[Union[int, str], Dict[str, Any]] = {
    **GROUP_MEMBER_ERRORS,
    409: error_response("Conflict", "Contact already in group"),
}




