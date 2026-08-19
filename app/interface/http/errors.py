"""DomainError → RFC 7807 problem+json mapper."""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
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
    for key in ("sku", "requested", "available"):
        if hasattr(exc, key):
            body[key] = getattr(exc, key)
    return JSONResponse(
        status_code=exc.http_status,
        content=body,
        media_type="application/problem+json",
    )


def _make_serializable(value: object) -> object:
    """Recursively convert any non-JSON-serializable value to a string."""
    if isinstance(value, dict):
        return {k: _make_serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_make_serializable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert a Pydantic RequestValidationError into an RFC 7807 problem+json response."""
    errors = exc.errors()
    first_msg = errors[0]["msg"] if errors else "Validation error"
    body: dict[str, object] = {
        "type": f"{PROBLEM_BASE_URL}/validation-error",
        "title": "Validation Error",
        "status": 422,
        "detail": first_msg,
        "errors": _make_serializable(errors),
    }
    return JSONResponse(
        status_code=422,
        content=body,
        media_type="application/problem+json",
    )
