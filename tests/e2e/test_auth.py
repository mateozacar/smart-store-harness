"""E2E tests: POST /api/v1/auth/login endpoint."""

from __future__ import annotations

import os

import httpx
import jwt
import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.interface.http.main import create_app

pytestmark = pytest.mark.e2e

_TEST_SECRET = "test-secret-key"
_TEST_EMAIL = "ada-auth@example.com"
_TEST_PASSWORD = "correct-horse"


@pytest.fixture(scope="module")
def app(pg_session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    """Create the FastAPI app wired to the test Postgres container."""
    os.environ.setdefault("SECRET_KEY", _TEST_SECRET)
    return create_app(session_factory=pg_session_factory)


async def _register_buyer(app: FastAPI, email: str, password: str) -> None:
    """Helper: register a buyer via the API."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/v1/customers",
            json={"email": email, "password": password},
        )
    assert resp.status_code == 201, f"Registration failed: {resp.text}"


# ---------------------------------------------------------------------------
# Scenario 1: Successful login returns access token
# ---------------------------------------------------------------------------


async def test_successful_login_returns_200_with_token(app: FastAPI) -> None:
    """Scenario: Correct credentials return 200 with access_token and token_type."""
    await _register_buyer(app, _TEST_EMAIL, _TEST_PASSWORD)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD},
        )

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


async def test_access_token_contains_sub_and_exp(app: FastAPI) -> None:
    """The access_token must decode to a JWT with 'sub' and 'exp' claims."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _TEST_EMAIL, "password": _TEST_PASSWORD},
        )

    token = response.json()["access_token"]
    # Decode without verifying signature for the e2e test (secret may differ from settings default)
    decoded = jwt.decode(token, options={"verify_signature": False})
    assert "sub" in decoded
    assert "exp" in decoded


# ---------------------------------------------------------------------------
# Scenario 2: Login with wrong password is rejected
# ---------------------------------------------------------------------------


async def test_wrong_password_returns_401_problem_json(app: FastAPI) -> None:
    """Scenario: Wrong password returns 401 with problem+json invalid-credentials."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _TEST_EMAIL, "password": "wrong-horse"},
        )

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/invalid-credentials")
    assert body["status"] == 401
    assert "access_token" not in body


# ---------------------------------------------------------------------------
# Scenario 3: Login with unknown email is rejected (no user enumeration)
# ---------------------------------------------------------------------------


async def test_unknown_email_returns_401_problem_json(app: FastAPI) -> None:
    """Scenario: Unknown email returns 401 identical to wrong-password case."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "anything"},
        )

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/invalid-credentials")
    assert "access_token" not in body


async def test_unknown_email_and_wrong_password_response_shapes_are_identical(
    app: FastAPI,
) -> None:
    """No user enumeration: wrong-password and unknown-email responses have the same shape."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        wrong_pw = await client.post(
            "/api/v1/auth/login",
            json={"email": _TEST_EMAIL, "password": "wrong"},
        )
        unknown_email = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost2@example.com", "password": "anything"},
        )

    assert wrong_pw.status_code == unknown_email.status_code == 401
    wp_body = wrong_pw.json()
    ue_body = unknown_email.json()
    # Same keys and problem type
    assert set(wp_body.keys()) == set(ue_body.keys())
    assert wp_body["type"] == ue_body["type"]
    assert wp_body["detail"] == ue_body["detail"]


# ---------------------------------------------------------------------------
# Scenario 4: Login with missing fields is rejected
# ---------------------------------------------------------------------------


async def test_missing_password_returns_422_problem_json(app: FastAPI) -> None:
    """Scenario: Request missing password field returns 422 problem+json."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": _TEST_EMAIL},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/validation-error")


async def test_missing_email_returns_422_problem_json(app: FastAPI) -> None:
    """Request missing email field returns 422 problem+json."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"password": "some-password"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


async def test_empty_body_returns_422(app: FastAPI) -> None:
    """Request with empty body returns 422."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/auth/login", json={})

    assert response.status_code == 422
