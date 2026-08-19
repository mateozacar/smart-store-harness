"""E2E tests: GET /api/v1/products endpoint."""

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
# Scenario 1: Buyer lists products with default pagination
# ---------------------------------------------------------------------------


async def test_default_pagination_returns_first_page(app: FastAPI) -> None:
    """GET /api/v1/products returns 200 with items ordered by created_at desc."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Seed three products in order SKU-A → SKU-B → SKU-C
        for sku in ("E2E-LST-A", "E2E-LST-B", "E2E-LST-C"):
            await client.post(
                "/api/v1/products",
                json={"sku": sku, "name": f"Product {sku}", "price": "10.00"},
            )

        response = await client.get("/api/v1/products")

    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body
    assert body["page"] == 1
    assert body["size"] == 20
    # Our three products must appear in the list (others may exist from concurrent tests)
    found_skus = [item["sku"] for item in body["items"]]
    # SKU-C was created last so must appear before SKU-A
    assert "E2E-LST-C" in found_skus
    assert "E2E-LST-A" in found_skus
    c_index = found_skus.index("E2E-LST-C")
    a_index = found_skus.index("E2E-LST-A")
    assert c_index < a_index, "E2E-LST-C (created last) must come before E2E-LST-A in desc order"
    assert body["total"] >= 3


# ---------------------------------------------------------------------------
# Scenario 3: Buyer requests a page beyond the last
# ---------------------------------------------------------------------------


async def test_empty_page_beyond_last_returns_metadata(app: FastAPI) -> None:
    """GET /api/v1/products?page=5&size=20 returns 200 with empty items."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/products", params={"page": 9999, "size": 20})

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["page"] == 9999
    assert body["size"] == 20
    assert body["total"] >= 0


# ---------------------------------------------------------------------------
# Scenario 4: Buyer sends an invalid price range
# ---------------------------------------------------------------------------


async def test_invalid_price_range_returns_problem_json_422(app: FastAPI) -> None:
    """GET /api/v1/products?min_price=50&max_price=10 returns 422 problem+json."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/v1/products",
            params={"min_price": "50", "max_price": "10"},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("invalid-price-range")
    assert body["status"] == 422
