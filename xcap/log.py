import os
from collections.abc import MutableMapping
from logging import FileHandler
from typing import Any, Dict, Optional, Union

from application import log
from application.system import makedirs
from fastapi import Request, Response

from xcap.configuration import LoggingConfig
from xcap.http_utils import get_client_ip


class AccessLog(object):
    access_type: Optional[str] = None

    def __init__(self, headers: Dict[str, str], body: Union[bytes, str, None] = None, code: int = 0):
        self.logger = access_file_logger

        self.headers = headers
        self.body = body
        self.code = code

    def _log(self) -> None:
        self.logger.info(f'\n{"-" * 2} {self.access_type} {"-" * 38}')
        for key, value in self.headers.items():
            self.logger.info(f'{key}: {value}')

        if self.body:
            content = self.body.decode('utf-8', errors='replace') if isinstance(self.body, bytes) else self.body
            self.logger.info("\n" + (content[:500] + "\n..." if len(content) > 500 else content) + "\n")
        elif isinstance(self, AccessLogResponse):
            self.logger.info("")

    def log(self) -> None:
        pass


class AccessLogRequest(AccessLog):
    access_type = "Request"

    def log(self) -> None:
        if self.code in LoggingConfig.log_request:
            self._log()


class AccessLogResponse(AccessLog):
    access_type = "Response"

    def log(self) -> None:
        if self.code in LoggingConfig.log_response:
            self._log()


access_logger = log.get_logger('access')
file_formatter = log.Formatter()
file_formatter.prefix_format = ''
file_handler = None

access_file_logger = log.get_logger('access.file')
access_file_logger.logger.setLevel(log.level.INFO)

if LoggingConfig.directory:
    if not os.path.exists(LoggingConfig.directory):
        try:
            makedirs(LoggingConfig.directory)
        except OSError as e:
            raise RuntimeError('Cannot create logging directory {}: {}'.format(LoggingConfig.directory, e))
    filename = os.path.join(LoggingConfig.directory, 'access.log')
    file_handler = FileHandler(filename)
    file_handler.setFormatter(file_formatter)
    access_logger.addHandler(file_handler)
    access_file_logger.addHandler(file_handler)
    access_file_logger.propagate = False


def get_request_version(scope: MutableMapping[str, Any]) -> str:
    request_type: str = scope.get("type") or "HTTP"
    http_version_value: str = scope.get("http_version") or "1.0"

    return f'{request_type.upper()}/{http_version_value.upper()}'


def log_access(request: Request, response: Response, body: Union[bytes, str]) -> None:
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent", "unknown")
    etag = response.headers.get("etag", None)
    method = request.method
    http_version = get_request_version(request.scope)
    path = request.url.path
    status_code = response.status_code
    access_logger.info(f"{client_ip} - \"{method} {path} {http_version}\" {status_code} {len(body)} {user_agent} {etag if etag else ''}")
