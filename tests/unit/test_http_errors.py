"""Unit tests for the HTTP error handler."""

from fastapi.testclient import TestClient

from app.domain.errors import DomainError
from app.interface.http.errors import PROBLEM_BASE_URL
from app.interface.http.main import create_app


def test_domain_error_handler_maps_to_problem_json() -> None:
    """domain_error_handler produces an RFC 7807 problem+json response."""
    app = create_app()

    @app.get("/test-error")
    async def _raise() -> None:
        raise DomainError("test-error", "Something bad happened")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/test-error")

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == f"{PROBLEM_BASE_URL}/domain-error"
    assert body["status"] == 422
    assert body["detail"] == "Something bad happened"


def test_problem_base_url_is_set() -> None:
    """PROBLEM_BASE_URL is non-empty."""
    assert PROBLEM_BASE_URL.startswith("https://")
