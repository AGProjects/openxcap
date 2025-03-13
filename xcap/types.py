from typing import Any, Callable, Coroutine, Union

from fastapi import Request

from xcap.configuration.datatypes import XCAPRootURI

CheckETagType = Callable[[Request, str, bool], None]
PublishFunction = Callable[[str, str], None]


PublishWrapper = Callable[[str, XCAPRootURI], Coroutine[Any, Any, None]]

