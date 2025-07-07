import re
from typing import Any, Generator, Optional

from pydantic import BaseModel, validator

try:
    from pydantic import GetCoreSchemaHandler
    from pydantic_core import core_schema
except ImportError:
    core_schema = None  # type: ignore
    GetCoreSchemaHandler = None  # type: ignore


class UserModel:
    REGEX = re.compile(r"^[\w.!%+\-]+@([\w\-]+\.)+[\w\-]{2,}$")

    @classmethod
    def __get_validators__(cls) -> Generator:
        yield cls.validate

    if core_schema:
        @classmethod
        def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler):
            """Fix JSON Schema generation for FastAPI"""
            return core_schema.str_schema(pattern=cls.REGEX.pattern)
    else:
        @classmethod
        def __modify_schema__(cls, field_schema: dict) -> None:
            field_schema.update(
                {
                    "type": "string",
                    "pattern": cls.REGEX.pattern,
                    "example": "user@example.com",
                }
            )

    @classmethod
    def validate(cls, value: str) -> str:
        if not isinstance(value, str):
            raise TypeError("User must be a string")
        if not cls.REGEX.match(value):
            raise ValueError(f"Invalid user: {value}")
        return f'sip:{value}'  # Return the valid SIP URL


class UserIconModel(BaseModel):
    user: UserModel
    data: str
    mime_type: str

    description: Optional[str] = None
    encoding: Optional[str] = None

    @validator('mime_type', pre=True)
    def lowercase_mime_type(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("mime_type is required and must be a non-empty string")
        if value not in ['image/jpeg', 'image/png', 'image/gif']:
            raise ValueError(f"Invalid mime_type: {value}. Allowed types are: 'image/jpeg', 'image/png', 'image/gif'")
        return value

    @validator('encoding', pre=True)
    def lowercase_encoding(cls, value):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("encoding is required and must be a non-empty string")
        value = value.lower()
        if value != 'base64':
            raise ValueError(f"Invalid encoding: {value}. Allowed encoding is: 'base64'")
        return value.lower()
