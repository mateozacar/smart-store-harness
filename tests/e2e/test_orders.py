"""E2E tests: POST /api/v1/orders endpoint.

Test Matrix coverage:
- Order placed with customer attached (e2e)
- Anonymous order placed without customer (e2e)
- Order rejected when customer does not exist (e2e)
- Order rejected when stock insufficient (e2e)
- Concurrent orders do not double-book (e2e)
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.interface.http.main import create_app

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def app(pg_session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    """Create the FastAPI app wired to the test Postgres container."""
    return create_app(session_factory=pg_session_factory)


async def _seed_product_and_inventory(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
    on_hand: int,
    reserved: int = 0,
) -> None:
    """Seed a product and corresponding inventory row."""
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
            {"id": product_id, "sku": sku, "name": f"E2E Product {sku}", "price": "9.99"},
        )
        await session.execute(
            text(
                "INSERT INTO inventory (sku, on_hand, reserved) VALUES (:sku, :on_hand, :reserved)"
            ),
            {"sku": sku, "on_hand": on_hand, "reserved": reserved},
        )


async def _seed_customer(
    session_factory: async_sessionmaker[AsyncSession],
    customer_id: str,
    email: str,
) -> None:
    """Seed a customer row."""
    async with session_factory() as session, session.begin():
        await session.execute(
            text("DELETE FROM customers WHERE id = :id"),
            {"id": customer_id},
        )
        await session.execute(
            text("INSERT INTO customers (id, email) VALUES (:id, :email)"),
            {"id": customer_id, "email": email},
        )


async def _get_reserved(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
) -> int:
    """Fetch the current reserved count for a SKU."""
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT reserved FROM inventory WHERE sku = :sku"),
            {"sku": sku},
        )
        row = result.fetchone()
        assert row is not None
        return int(row[0])


# ---------------------------------------------------------------------------
# Gherkin scenario: Order placed with customer attached
# ---------------------------------------------------------------------------


async def test_place_order_with_customer_returns_201(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Order placed with customer attached.

    POST returns 201, order has customer_id set, inventory is reserved.
    """
    sku = "E2E-CUST-A"
    customer_id = str(uuid.uuid4())
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=10, reserved=0)
    await _seed_customer(pg_session_factory, customer_id, f"e2e-cust-a-{customer_id}@test.com")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            json={"customer_id": customer_id, "lines": [{"sku": sku, "quantity": 3}]},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["customer_id"] == customer_id
    assert len(body["lines"]) == 1
    assert body["lines"][0]["sku"] == sku
    assert body["lines"][0]["quantity"] == 3
    assert "location" in response.headers

    reserved = await _get_reserved(pg_session_factory, sku)
    assert reserved == 3


# ---------------------------------------------------------------------------
# Gherkin scenario: Anonymous order placed without customer
# ---------------------------------------------------------------------------


async def test_place_order_anonymous_returns_201(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Anonymous order placed without customer.

    POST without customer_id returns 201 with customer_id null.
    """
    sku = "E2E-ANON-B"
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=5, reserved=0)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            json={"lines": [{"sku": sku, "quantity": 2}]},
        )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert body["customer_id"] is None

    reserved = await _get_reserved(pg_session_factory, sku)
    assert reserved == 2


# ---------------------------------------------------------------------------
# Gherkin scenario: Order rejected when customer does not exist
# ---------------------------------------------------------------------------


async def test_place_order_unknown_customer_returns_422(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Order rejected when customer does not exist.

    Returns 422 problem+json with type 'customer-not-found'.
    No order persisted, inventory unchanged.
    """
    sku = "E2E-NOCUST-C"
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=5, reserved=0)

    nonexistent_id = str(uuid.uuid4())
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            json={"customer_id": nonexistent_id, "lines": [{"sku": sku, "quantity": 1}]},
        )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/customer-not-found")

    reserved = await _get_reserved(pg_session_factory, sku)
    assert reserved == 0


# ---------------------------------------------------------------------------
# Gherkin scenario: Order rejected when stock insufficient
# ---------------------------------------------------------------------------


async def test_place_order_insufficient_stock_returns_409(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Order rejected when stock insufficient.

    on_hand=2, reserved=1 → available=1; requesting 2 returns 409.
    """
    sku = "E2E-INSUF-D"
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=2, reserved=1)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            json={"lines": [{"sku": sku, "quantity": 2}]},
        )

    assert response.status_code == 409
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/insufficient-stock")
    assert body["sku"] == sku
    assert body["requested"] == 2
    assert body["available"] == 1

    reserved = await _get_reserved(pg_session_factory, sku)
    assert reserved == 1  # unchanged


# ---------------------------------------------------------------------------
# Gherkin scenario: Concurrent orders do not double-book (wire format)
# ---------------------------------------------------------------------------


async def test_concurrent_order_rejection_wire_format(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Concurrent orders do not double-book.

    Two requests for 1 unit each on stock of 1: exactly one 201 and one 409.
    The 409 response is valid problem+json.
    """
    sku = "E2E-CONCUR-E"
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=1, reserved=0)

    async def _post_order() -> int:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            r = await client.post(
                "/api/v1/orders",
                json={"lines": [{"sku": sku, "quantity": 1}]},
            )
            return r.status_code

    status_codes = await asyncio.gather(_post_order(), _post_order())

    assert sorted(status_codes) == [201, 409], (
        f"Expected one 201 and one 409, got {sorted(status_codes)}"
    )

    final_reserved = await _get_reserved(pg_session_factory, sku)
    assert final_reserved == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_place_order_rejects_missing_lines(app: FastAPI) -> None:
    """Request without lines field is rejected with 422."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/orders", json={"customer_id": None})

    assert response.status_code == 422


async def test_place_order_rejects_empty_lines(app: FastAPI) -> None:
    """Request with empty lines list is rejected with 422."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/orders", json={"lines": []})

    assert response.status_code == 422


async def test_place_order_rejects_zero_quantity(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Request with quantity=0 is rejected with 422 (Pydantic gt=0 constraint)."""
    sku = "E2E-ZEROQUANTITY"
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=10, reserved=0)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            json={"lines": [{"sku": sku, "quantity": 0}]},
        )

    assert response.status_code == 422


async def test_place_order_rejects_extra_fields(app: FastAPI) -> None:
    """Request with extra unknown fields is rejected (Pydantic extra='forbid')."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            json={"lines": [{"sku": "SKU-X", "quantity": 1}], "unknown_field": "value"},
        )

    assert response.status_code == 422


async def test_place_order_returns_location_header(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Successful order creation returns Location header pointing to the order."""
    sku = "E2E-LOC-F"
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=10, reserved=0)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/orders",
            json={"lines": [{"sku": sku, "quantity": 1}]},
        )

    assert response.status_code == 201
    body = response.json()
    assert response.headers["location"] == f"/api/v1/orders/{body['id']}"
