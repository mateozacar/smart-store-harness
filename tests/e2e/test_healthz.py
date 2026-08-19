"""E2E test: health endpoint returns ok."""

import httpx
import pytest
from fastapi import FastAPI

from app.interface.http.main import create_app

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def app() -> FastAPI:
    """Create the FastAPI app for testing."""
    return create_app()


async def test_healthz_returns_ok(app: FastAPI) -> None:
    """Health endpoint returns 200 with body 'ok'."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == "ok"
