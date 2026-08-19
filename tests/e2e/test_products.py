"""E2E tests: POST /api/v1/products endpoint."""

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


async def test_creates_product_and_returns_201(app: FastAPI) -> None:
    """Scenario: Product created with valid SKU, name, and price."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/products",
            json={"sku": "WIDGET-01", "name": "Blue Widget", "price": "19.99"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "WIDGET-01"
    assert body["name"] == "Blue Widget"
    assert body["price"] == "19.99"
    assert "location" in response.headers
    assert response.headers["location"] == "/api/v1/products/WIDGET-01"


async def test_creates_product_with_zero_price(app: FastAPI) -> None:
    """Scenario: Product with zero price is accepted."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/products",
            json={"sku": "FREE-SAMPLE", "name": "Free Sample", "price": "0.00"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "FREE-SAMPLE"
    assert body["price"] == "0.00"


async def test_rejects_duplicate_sku_with_409(app: FastAPI) -> None:
    """Scenario: Creation rejected when SKU already exists."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Create the product first
        await client.post(
            "/api/v1/products",
            json={"sku": "SKU-DUP", "name": "Original", "price": "10.00"},
        )
        # Attempt to create again with the same SKU
        response = await client.post(
            "/api/v1/products",
            json={"sku": "SKU-DUP", "name": "Duplicate", "price": "20.00"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["type"].endswith("sku-conflict")
    assert response.headers["content-type"] == "application/problem+json"


async def test_rejects_negative_price_with_422(app: FastAPI) -> None:
    """Scenario: Creation rejected for negative price."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/products",
            json={"sku": "NEG-PRICE", "name": "Bad Product", "price": "-5.00"},
        )

    assert response.status_code == 422
    body = response.json()
    assert "type" in body
    assert response.headers["content-type"] == "application/problem+json"
