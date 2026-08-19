"""FastAPI application factory."""

from __future__ import annotations

import structlog
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.errors import DomainError
from app.interface.http.dependencies import set_session_factory
from app.interface.http.errors import domain_error_handler, validation_error_handler
from app.interface.http.routers.customers import router as customers_router
from app.interface.http.routers.products import router as products_router

logger = structlog.get_logger()


def create_app(
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> FastAPI:
    """Build and configure the FastAPI application.

    Args:
        session_factory: Optional session factory for testing. When provided,
            it overrides the default production session factory.
    """
    if session_factory is not None:
        set_session_factory(session_factory)

    app = FastAPI(
        title="Smart Store API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]

    app.include_router(products_router)
    app.include_router(customers_router)

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> str:
        """Liveness probe."""
        return "ok"

    return app
