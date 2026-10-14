"""E2E tests: POST /api/v1/customers and DELETE /api/v1/customers/{id} endpoints."""

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


async def _seed_product_and_inventory(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
    on_hand: int,
) -> None:
    """Seed a product and corresponding inventory row directly in the DB."""
    product_id = str(uuid.uuid4())
    async with session_factory() as session, session.begin():
        await session.execute(text("DELETE FROM inventory WHERE sku = :sku"), {"sku": sku})
        await session.execute(text("DELETE FROM order_lines WHERE sku = :sku"), {"sku": sku})
        await session.execute(text("DELETE FROM products WHERE sku = :sku"), {"sku": sku})
        await session.execute(
            text("INSERT INTO products (id, sku, name, price) VALUES (:id, :sku, :name, :price)"),
            {"id": product_id, "sku": sku, "name": f"Test {sku}", "price": "9.99"},
        )
        await session.execute(
            text("INSERT INTO inventory (sku, on_hand, reserved) VALUES (:sku, :on_hand, 0)"),
            {"sku": sku, "on_hand": on_hand},
        )


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
            json={"email": "buyer@example.com"},
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
            json={"email": "Alice@Example.COM"},
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
        await client.post("/api/v1/customers", json={"email": "taken-exact@example.com"})
        response = await client.post(
            "/api/v1/customers",
            json={"email": "taken-exact@example.com"},
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
        await client.post("/api/v1/customers", json={"email": "taken-ci@example.com"})
        response = await client.post(
            "/api/v1/customers",
            json={"email": "TAKEN-CI@EXAMPLE.COM"},
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
            json={"email": "not-an-email"},
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
            json={"email": "valid@example.com", "name": "unexpected"},
        )

    assert response.status_code == 422


async def test_post_customers_rejects_missing_email(app: FastAPI) -> None:
    """Request without email field is rejected with 422."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/v1/customers", json={})

    assert response.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /api/v1/customers/{id} — happy-path
# (Test Matrix: "Successful customer deletion")
# ---------------------------------------------------------------------------


async def test_delete_customer_returns_204(app: FastAPI) -> None:
    """Scenario: Successful customer deletion removes the customer and returns 204."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/v1/customers",
            json={"email": "to-delete@example.com"},
        )
        assert create_resp.status_code == 201
        customer_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/v1/customers/{customer_id}")

    assert delete_resp.status_code == 204
    assert delete_resp.content == b""


async def test_delete_customer_row_is_actually_removed(app: FastAPI) -> None:
    """After DELETE the customer cannot be re-created without conflict (proves removal)."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        create_resp = await client.post(
            "/api/v1/customers",
            json={"email": "deleted-and-recreated@example.com"},
        )
        assert create_resp.status_code == 201
        customer_id = create_resp.json()["id"]

        await client.delete(f"/api/v1/customers/{customer_id}")

        # Now re-register the same email — should succeed (no conflict)
        re_create_resp = await client.post(
            "/api/v1/customers",
            json={"email": "deleted-and-recreated@example.com"},
        )

    assert re_create_resp.status_code == 201


# ---------------------------------------------------------------------------
# DELETE /api/v1/customers/{id} — 404 not-found
# (Test Matrix: "Delete non-existent customer")
# ---------------------------------------------------------------------------


async def test_delete_nonexistent_customer_returns_404(app: FastAPI) -> None:
    """Scenario: Deleting a non-existent customer returns 404 problem+json."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.delete("/api/v1/customers/00000000-0000-0000-0000-000000000099")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert body["type"].endswith("/customer-not-found")
    assert body["status"] == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/customers/{id} — 409 active orders
# (Test Matrix: "Delete customer with active orders")
# ---------------------------------------------------------------------------


async def test_delete_customer_with_pending_order_returns_409(
    app: FastAPI,
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Customer with a PENDING order cannot be deleted — returns 409."""
    sku = f"SKU-DELACT-{uuid.uuid4().hex[:6].upper()}"
    await _seed_product_and_inventory(pg_session_factory, sku, on_hand=10)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Register a customer
        cust_resp = await client.post(
            "/api/v1/customers",
            json={"email": f"active-order-{uuid.uuid4().hex[:6]}@example.com"},
        )
        assert cust_resp.status_code == 201
        customer_id = cust_resp.json()["id"]

        # Place an order referencing the customer
        order_resp = await client.post(
            "/api/v1/orders",
            json={"customer_id": customer_id, "lines": [{"sku": sku, "quantity": 1}]},
        )
        assert order_resp.status_code == 201

        # Attempt to delete — must fail with 409
        delete_resp = await client.delete(f"/api/v1/customers/{customer_id}")

    assert delete_resp.status_code == 409
    assert delete_resp.headers["content-type"] == "application/problem+json"
    body = delete_resp.json()
    assert body["type"].endswith("/customer-has-active-orders")
    assert body["status"] == 409
