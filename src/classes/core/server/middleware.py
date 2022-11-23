from typing import Optional

from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    DispatchFunction,
    RequestResponseEndpoint,
)
from starlette.types import ASGIApp

from . import logger


class LogWare(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, dispatch: Optional[DispatchFunction] = None):
        super().__init__(app, dispatch)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        logger.debug(f"{request.method} {request.url}")
        resp = await call_next(request)
        logger.trace(resp)
        return resp
