"""E2E tests: POST /api/v1/customers endpoint."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.interface.http.main import create_app

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def app(pg_session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    """Create the FastAPI app wired to the test Postgres container."""
    return create_app(session_factory=pg_session_factory)


# ---------------------------------------------------------------------------
# Happy-path scenarios
# ---------------------------------------------------------------------------


async def test_post_customers_returns_201(app: FastAPI) -> None:
    """Scenario: Register customer with a valid new email.

    POST returns 201 with id, email, and Location header.
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/customers",
            json={"email": "buyer@example.com", "password": "pw-test"},
        )

    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["email"] == "buyer@example.com"
    assert "location" in response.headers
    assert response.headers["location"] == f"/api/v1/customers/{body['id']}"


async def test_post_customers_normalizes_email_to_lowercase(app: FastAPI) -> None:
    """Scenario: Email with uppercase letters is normalized to lowercase.

    POST with mixed-case email returns 201 with the normalized email.
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/customers",
            json={"email": "Alice@Example.COM", "password": "pw-test"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alice@example.com"


# ---------------------------------------------------------------------------
# Conflict scenarios
# (Test Matrix: "Duplicate email exact match", "Duplicate email different casing")
# ---------------------------------------------------------------------------


async def test_post_customers_409_on_duplicate_email(app: FastAPI) -> None:
    """Scenario: Duplicate email exact match is rejected with 409.

    The second POST with the same email returns 409 problem+json
    with type ending in '/email-conflict'.
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/customers",
            json={"email": "taken-exact@example.com", "password": "pw-test"},
        )
        response = await client.post(
            "/api/v1/customers",
            json={"email": "taken-exact@example.com", "password": "pw-test"},
        )

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/email-conflict")


async def test_post_customers_409_case_insensitive_duplicate(app: FastAPI) -> None:
    """Scenario: Duplicate email with different casing is rejected with 409.

    'taken-ci@example.com' and 'TAKEN-CI@EXAMPLE.COM' normalize to the
    same address; the second attempt must return 409.
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        await client.post(
            "/api/v1/customers",
            json={"email": "taken-ci@example.com", "password": "pw-test"},
        )
        response = await client.post(
            "/api/v1/customers",
            json={"email": "TAKEN-CI@EXAMPLE.COM", "password": "pw-test"},
        )

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/email-conflict")


# ---------------------------------------------------------------------------
# Validation failure scenario
# (Test Matrix: "Malformed email")
# ---------------------------------------------------------------------------


async def test_post_customers_422_on_malformed_email(app: FastAPI) -> None:
    """Scenario: Malformed email is rejected with 422 problem+json.

    A POST with 'not-an-email' returns 422 with type ending '/invalid-email'.
    """
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/customers",
            json={"email": "not-an-email", "password": "pw-test"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/invalid-email")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_post_customers_rejects_extra_fields(app: FastAPI) -> None:
    """Request with unknown fields is rejected (Pydantic extra='forbid')."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/customers",
            json={"email": "valid@example.com", "password": "pw-test", "name": "unexpected"},
        )

    assert response.status_code == 422


async def test_post_customers_rejects_missing_email(app: FastAPI) -> None:
    """Request without email field is rejected with 422."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/customers", json={})

    assert response.status_code == 422
