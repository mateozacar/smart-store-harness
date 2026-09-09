"""E2E tests: GET /api/v1/products/{sku} endpoint."""

from __future__ import annotations

import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.interface.http.main import create_app

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def app(pg_session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    """Create the FastAPI app wired to the test Postgres container."""
    return create_app(session_factory=pg_session_factory)


async def _seed_product(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
    name: str = "Widget",
    price: str = "9.99",
) -> str:
    """Insert a product row and return its id."""
    product_id = str(uuid.uuid4())
    async with session_factory() as session, session.begin():
        await session.execute(
            text("DELETE FROM inventory WHERE sku = :sku"),
            {"sku": sku},
        )
        await session.execute(
            text("DELETE FROM order_lines WHERE sku = :sku"),
            {"sku": sku},
        )
        await session.execute(
            text("DELETE FROM products WHERE sku = :sku"),
            {"sku": sku},
        )
        await session.execute(
            text("INSERT INTO products (id, sku, name, price) VALUES (:id, :sku, :name, :price)"),
            {"id": product_id, "sku": sku, "name": name, "price": price},
        )
    return product_id


async def _seed_inventory(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
    on_hand: int,
    reserved: int = 0,
) -> None:
    """Insert an inventory row for a SKU."""
    async with session_factory() as session, session.begin():
        await session.execute(
            text("DELETE FROM inventory WHERE sku = :sku"),
            {"sku": sku},
        )
        await session.execute(
            text(
                "INSERT INTO inventory (sku, on_hand, reserved) VALUES (:sku, :on_hand, :reserved)"
            ),
            {"sku": sku, "on_hand": on_hand, "reserved": reserved},
        )


async def test_get_product_detail_returns_available(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Product detail returned with available stock."""
    await _seed_product(pg_session_factory, "DETAIL-01", "Widget", "9.99")
    await _seed_inventory(pg_session_factory, "DETAIL-01", on_hand=10, reserved=3)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/products/DETAIL-01")

    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "DETAIL-01"
    assert body["name"] == "Widget"
    assert body["price"] == "9.99"
    assert body["available"] == 7


async def test_get_product_detail_no_inventory_row(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Product with no inventory row returns available=0."""
    await _seed_product(pg_session_factory, "DETAIL-02", "No Stock Product", "5.00")
    # No inventory row seeded for DETAIL-02

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/products/DETAIL-02")

    assert response.status_code == 200
    body = response.json()
    assert body["sku"] == "DETAIL-02"
    assert body["available"] == 0


async def test_get_product_detail_unknown_sku_returns_404(app: FastAPI) -> None:
    """Scenario: Unknown SKU returns 404 problem+json."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/products/GHOST-01")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("product-not-found")
    assert body["status"] == 404
    assert body["sku"] == "GHOST-01"


async def test_get_product_detail_available_with_full_reservation(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Edge case: available=0 when all stock is reserved."""
    await _seed_product(pg_session_factory, "DETAIL-03", "Sold Out", "1.00")
    await _seed_inventory(pg_session_factory, "DETAIL-03", on_hand=1, reserved=1)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/products/DETAIL-03")

    assert response.status_code == 200
    assert response.json()["available"] == 0
