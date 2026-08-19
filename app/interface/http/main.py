"""FastAPI application factory."""

import structlog
from fastapi import FastAPI

from app.domain.errors import DomainError
from app.interface.http.errors import domain_error_handler

logger = structlog.get_logger()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Smart Store API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> str:
        """Liveness probe."""
        return "ok"

    return app
