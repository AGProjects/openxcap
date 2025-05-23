import threading
from datetime import datetime

import uvicorn
from application import log
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from starlette.background import BackgroundTask, BackgroundTasks
from starlette.middleware.base import BaseHTTPMiddleware
from twisted.internet import asyncioreactor, reactor

from xcap import (__author__, __description__, __fullname__, __url__,
                  __version__)
from xcap.configuration import ServerConfig, TLSConfig
from xcap.db.initialize import init_db
from xcap.errors import HTTPError, ResourceNotFound, XCAPError
from xcap.log import AccessLogRequest, AccessLogResponse, log_access


class LogRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        body = await request.body()
        request.state.body = body
        response = await call_next(request)

        response.headers['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        res_body = b''.join(chunks)

        request_log = AccessLogRequest(dict(request.headers), body, response.status_code)
        response_log = AccessLogResponse(dict(response.headers), res_body, response.status_code)

        task = BackgroundTasks()
        task.add_task(BackgroundTask(log_access, request, response, res_body))
        task.add_task(BackgroundTask(request_log.log))
        task.add_task(BackgroundTask(response_log.log))

        return Response(content=res_body, status_code=response.status_code,
                        headers=dict(response.headers), media_type=response.media_type, background=task)


class XCAPApp(FastAPI):
    backend: str = ''

    def __init__(self):
        super().__init__(
            title=__fullname__,
            description=f"{__description__} [{__url__}]({__url__})",
            version=__version__
        )
        self.add_middleware(LogRequestMiddleware)
        from xcap.routes import xcap_routes
        self.include_router(xcap_routes.router)
        try:
            from xcap.routes import api_routes
        except ImportError as e:
            log.warning(f"REST API routes not loaded due to import error: {e}")
        else:
            self.include_router(api_routes.router)
        # self.app.include_router(user_routes.router)  # Uncomment if user_routes is needed
        self.on_event("startup")(self.startup)
        self.on_event("shutdown")(self.shutdown_reactor)
        self.add_exception_handler(ResourceNotFound, self.resource_not_found_handler)
        self.add_exception_handler(HTTPError, self.http_error_handler)
        self.add_exception_handler(XCAPError, self.http_error_handler)
        self.add_api_route("/", self.read_root, methods=["GET"])

    async def http_error_handler(self, request: Request, exc: HTTPError) -> Response:
        return exc.response

    async def resource_not_found_handler(self, request: Request, exc: ResourceNotFound) -> Response:
        if exc.headers:
            content_type = exc.headers.get("Content-Type", "text/plain")

        if content_type == "application/json":
            return JSONResponse(
                content={"detail": exc.detail},
                status_code=exc.status_code,
                headers=exc.headers
            )
        elif content_type == "text/html":
            return HTMLResponse(
                content=f"<html><body><h1>{exc.detail}</h1></body></html>",
                status_code=exc.status_code,
                headers=exc.headers
            )
        else:
            # Default to plain text if no valid Content-Type is provided
            return PlainTextResponse(
                content=exc.detail,
                status_code=exc.status_code,
                headers=exc.headers
            )

    async def startup(self):
        uvi_logger = log.get_logger('uvicorn.error')
        log.get_logger().setLevel(uvi_logger.level)
        log.Formatter.prefix_format = '{record.levelname:<8s} '
        log.get_logger('aiosqlite').setLevel(log.level.INFO)

        init_db()

        if ServerConfig.backend in ['SIPThor', 'OpenSIPS']:
            twisted_thread = threading.Thread(target=self._start_reactor, daemon=True)
            twisted_thread.name = 'TwistedReactor'
            twisted_thread.start()

        self.backend = ServerConfig.backend

        log.info("OpenXCAP app is running...")

    async def shutdown_reactor(self):
        if reactor.running:
            if self.backend == 'SIPThor':
                from xcap.appusage import ServerConfig
                ServerConfig.backend.XCAPProvisioning().stop()
            else:
                reactor.callFromThread(reactor.stop)

    def _start_reactor(self):
        from xcap.appusage import ServerConfig
        reactor.run(installSignalHandlers=ServerConfig.backend.installSignalHandlers)

    async def read_root(self):
        return {"message": "Welcome to OpenXCAP!"}


class XCAPServer():
    def __init__(self):
        self.config = ServerConfig

    def run(self, debug=False):
        log_config = uvicorn.config.LOGGING_CONFIG
        log_config["loggers"]["uvicorn"] = {"handlers": []}
        log_config["loggers"]["uvicorn.error"] = {"handlers": []}
        log_config["loggers"]["uvicorn.access"] = {"handlers": []}

        config = {
            'factory': True,
            'host': self.config.address,
            'port': self.config.port,
            'reload': debug,
            'log_level': 'debug' if debug else 'info',
            'workers': 1,
            'access_log': False,
            'log_config': log_config,
            'headers': [('server', f'{__fullname__}/{__version__}')]
        }

        certificate, private_key = TLSConfig.certificate, TLSConfig.private_key
        if self.config.root.startswith('https'):
            if certificate is None or private_key is None:
                log.warning('The TLS certificate/key could not be loaded, not listening on https')
            else:
                log.info('Enabling HTTPS')
                config['ssl_certfile'] = certificate.filename
                config['ssl_keyfile'] = private_key.filename

        uvicorn.run("xcap.server:XCAPApp", **config)
