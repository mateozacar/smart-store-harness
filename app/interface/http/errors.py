"""DomainError → RFC 7807 problem+json mapper."""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.errors import DomainError

PROBLEM_BASE_URL = "https://smart-store.example/problems"


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    """Convert a DomainError into an RFC 7807 problem+json response."""
    body: dict[str, object] = {
        "type": f"{PROBLEM_BASE_URL}/{exc.problem_type}",
        "title": exc.problem_type.replace("-", " ").title(),
        "status": exc.http_status,
        "detail": exc.detail,
    }
    # Include any extra machine-readable fields attached by the subclass.
    for key in ("code", "sku", "requested", "available"):
        if hasattr(exc, key) and key not in ("code",):
            body[key] = getattr(exc, key)
    return JSONResponse(
        status_code=exc.http_status,
        content=body,
        media_type="application/problem+json",
    )
