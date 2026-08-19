"""Integration test: concurrent orders do not double-book inventory.

Test Matrix coverage:
- Concurrent orders do not double-book (integration)
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.place_order import PlaceOrderCommand, PlaceOrderUseCase
from app.domain.inventory.entities import InsufficientStockError
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_inventory(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
    on_hand: int,
    reserved: int = 0,
) -> None:
    """Seed an inventory row, inserting or updating as needed."""
    async with session_factory() as session, session.begin():
        # Upsert: delete + insert to avoid conflicts from repeated runs.
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


async def _seed_product(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
) -> None:
    """Seed a product row that order_lines.sku FK references."""
    product_id = str(uuid.uuid4())
    async with session_factory() as session, session.begin():
        await session.execute(
            text("DELETE FROM products WHERE sku = :sku"),
            {"sku": sku},
        )
        await session.execute(
            text("INSERT INTO products (id, sku, name, price) VALUES (:id, :sku, :name, :price)"),
            {"id": product_id, "sku": sku, "name": f"Product {sku}", "price": "9.99"},
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
        assert row is not None, f"No inventory row for SKU '{sku}'"
        return int(row[0])


async def _place_one(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
    qty: int,
) -> bool:
    """Attempt to place an order for `qty` units of `sku`. Return True on success."""
    uow = SqlAlchemyUnitOfWork(session_factory)
    use_case = PlaceOrderUseCase(uow)
    try:
        await use_case.execute(PlaceOrderCommand(customer_id=None, lines=((sku, qty),)))
        return True
    except InsufficientStockError:
        return False


# ---------------------------------------------------------------------------
# Gherkin scenario: Concurrent orders do not double-book
# ---------------------------------------------------------------------------


async def test_concurrent_orders_do_not_double_book(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Concurrent orders do not double-book.

    on_hand=1, reserved=0 → available=1.
    Two concurrent requests each for 1 unit: exactly one must succeed,
    the other must get InsufficientStockError.
    reserved ends at exactly 1, never 2.
    """
    sku = "SKU-CONCUR-1"
    await _seed_product(pg_session_factory, sku)
    await _seed_inventory(pg_session_factory, sku, on_hand=1, reserved=0)

    results = await asyncio.gather(
        _place_one(pg_session_factory, sku, 1),
        _place_one(pg_session_factory, sku, 1),
    )

    assert sorted(results) == [False, True], (
        f"Expected exactly one success and one failure, got {results}"
    )
    final_reserved = await _get_reserved(pg_session_factory, sku)
    assert final_reserved == 1, f"reserved should be 1 but got {final_reserved}"


# ---------------------------------------------------------------------------
# Happy-path integration: customer-attached order persists correctly
# ---------------------------------------------------------------------------


async def test_order_with_customer_persisted_in_db(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Order with customer_id is saved to the DB with the correct FK."""
    sku = "SKU-CUST-INT"
    await _seed_product(pg_session_factory, sku)
    await _seed_inventory(pg_session_factory, sku, on_hand=10, reserved=0)

    # Register a customer first
    customer_id = str(uuid.uuid4())
    async with pg_session_factory() as session, session.begin():
        await session.execute(
            text("INSERT INTO customers (id, email) VALUES (:id, :email)"),
            {"id": customer_id, "email": f"inttest-{customer_id}@example.com"},
        )

    uow = SqlAlchemyUnitOfWork(pg_session_factory)
    use_case = PlaceOrderUseCase(uow)
    order = await use_case.execute(PlaceOrderCommand(customer_id=customer_id, lines=((sku, 2),)))

    # Verify in DB
    async with pg_session_factory() as session:
        result = await session.execute(
            text("SELECT customer_id, status FROM orders WHERE id = :id"),
            {"id": order.id},
        )
        row = result.fetchone()

    assert row is not None
    assert row[0] == customer_id
    assert row[1] == "PENDING"

    final_reserved = await _get_reserved(pg_session_factory, sku)
    assert final_reserved == 2
