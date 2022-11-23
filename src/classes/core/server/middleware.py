import time
from typing import Awaitable, Callable, Optional

from fastapi import Request
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    DispatchFunction,
    RequestResponseEndpoint,
)
from starlette.responses import StreamingResponse
from starlette.types import ASGIApp

from . import logger


class RequestLog(BaseHTTPMiddleware):
    """Log request and response"""

    def __init__(self, app: ASGIApp, dispatch: Optional[DispatchFunction] = None):
        super().__init__(app, dispatch)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[StreamingResponse]],
    ):
        logger.debug(f"{request.method} {request.url}")
        resp = await call_next(request)

        resp_body = [section async for section in resp.body_iterator]
        resp.body_iterator = iterate_in_threadpool(iter(resp_body))
        resp_data = resp_body[0].decode()  # type: ignore
        logger.trace(resp_data)

        return resp


class ErrorLog(BaseHTTPMiddleware):
    """Log Errors"""

    def __init__(self, app: ASGIApp, dispatch: Optional[DispatchFunction] = None):
        super().__init__(app, dispatch)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[StreamingResponse]],
    ):
        try:
            resp = await call_next(request)
            return resp
        except:
            logger.exception("")
            raise


class PerformanceLog(BaseHTTPMiddleware):
    """Measure response time"""

    def __init__(self, app: ASGIApp, dispatch: Optional[DispatchFunction] = None):
        super().__init__(app, dispatch)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[StreamingResponse]],
    ):
        start = time.time()
        resp = await call_next(request)
        end = time.time()

        elapsed_ms = (end - start) * 1000
        logger.debug(f"Response took {elapsed_ms:.0f}ms")
        return resp
