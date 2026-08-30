from __future__ import annotations

import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.core.errors import DomainError
from app.core.logging import get_logger, request_id_ctx

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id and emits one structured access log per request.

    The id is echoed back in ``X-Request-Id`` so a shopper reporting a problem
    can hand support a string that maps directly to a log line.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        request_id_ctx.set(request_id)
        started = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-Id"] = request_id
        response.headers["Server-Timing"] = f"app;dur={duration_ms}"
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response


async def domain_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Single translation point from domain errors to HTTP.

    Services raise vocabulary from their own domain; only this function knows
    status codes. The body shape is stable across every endpoint so the client
    has exactly one error contract to handle.
    """
    assert isinstance(exc, DomainError)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message_key": exc.message_key,
                "detail": str(exc),
                "context": exc.context,
            },
            "request_id": request_id_ctx.get(),
        },
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "internal_error", "message_key": "errors.internal"},
            "request_id": request_id_ctx.get(),
        },
    )
