from abc import ABC, abstractmethod
from typing import Callable, Optional, Union

from pydantic import BaseModel
from starlette.background import BackgroundTask, BackgroundTasks

from xcap.uri import XCAPUri


class CustomBaseModel(BaseModel):
    def __init__(self, *args, **kwargs):
        # Get the field names from the class
        field_names = list(self.__annotations__.keys())
        # Check if we have the right number of positional arguments
        if len(args) > len(field_names):
            raise ValueError(f"Too many positional arguments. Expected at most {len(field_names)}")

        # Assign positional arguments to keyword arguments dynamically
        for i, field in enumerate(field_names):
            if i < len(args):  # Only assign if we have enough positional arguments
                kwargs[field] = args[i]

        # Now call the parent __init__ method to handle the rest
        super().__init__(**kwargs)


class StatusResponse(CustomBaseModel):
    code: int
    etag: Optional[str] = None
    data: Optional[bytes] = None  # If this is binary data, it should be bytes
    old_etag: Optional[str] = None
    background: Union[BackgroundTasks, BackgroundTask, None] = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def succeed(self):
        return 200 <= self.code <= 299

    class Config:
        arbitrary_types_allowed = True


class BackendInterface(ABC):

    def _normalize_document_path(self, uri):
        if uri.application_id in ("pres-rules", "org.openmobilealliance.pres-rules"):
            # some clients e.g. counterpath's eyebeam save presence rules under
            # different filenames between versions and they expect to find the same
            # information, thus we are forcing all presence rules documents to be
            # saved under "index.xml" default filename
            uri.doc_selector.document_path = "index.xml"

    @abstractmethod
    async def get_document(self, uri: XCAPUri, check_etag: Callable) -> Optional[StatusResponse]:
        """Retrieve data for a specific resource."""
        pass

    @abstractmethod
    async def put_document(self, uri: XCAPUri, document: bytes, check_etag: Callable) -> Optional[StatusResponse]:
        """Retrieve data for a specific resource."""
        pass

    @abstractmethod
    async def delete_document(self, uri: XCAPUri, check_etag: Callable) -> Optional[StatusResponse]:
        """Retrieve data for a specific resource."""
        pass
