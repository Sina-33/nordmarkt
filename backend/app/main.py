from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from app.api.middleware import (
    RequestContextMiddleware,
    domain_error_handler,
    unhandled_error_handler,
)
from app.api.routers import cart, catalog, checkout, identity, webhooks
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.logging import configure_logging, get_logger
from app.db.session import dispose_engine, get_engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(debug=settings.debug)

    app.state.redis = Redis.from_url(str(settings.redis_url), decode_responses=True)
    logger.info("api_starting", environment=settings.environment)
    try:
        yield
    finally:
        await app.state.redis.aclose()
        await dispose_engine()
        logger.info("api_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Nordmarkt API",
        version="0.3.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/docs" if settings.environment != "production" else None,
        openapi_url="/openapi.json" if settings.environment != "production" else None,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "Server-Timing"],
    )

    app.add_exception_handler(DomainError, domain_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    for router in (catalog.router, cart.router, identity.router, checkout.router, webhooks.router):
        app.include_router(router, prefix="/api/v1")

    @app.get("/health/live", tags=["ops"])
    async def liveness() -> dict[str, str]:
        """Is the process up? Deliberately checks nothing external.

        A liveness probe that touches the database restarts healthy pods during
        a database blip and turns a small outage into a large one.
        """
        return {"status": "ok"}

    @app.get("/health/ready", tags=["ops"])
    async def readiness() -> dict[str, object]:
        """Can this instance serve traffic? Checks its dependencies."""
        checks: dict[str, object] = {}
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["database"] = f"error: {type(exc).__name__}"
        try:
            await app.state.redis.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {type(exc).__name__}"

        checks["status"] = "ok" if all(v == "ok" for k, v in checks.items() if k != "status") else "degraded"
        return checks

    return app


app = create_app()
