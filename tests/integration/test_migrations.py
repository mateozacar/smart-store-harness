"""Integration test: migrations create four core tables with PRD invariants."""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def test_tables_exist(pg_engine: AsyncEngine) -> None:
    """After alembic upgrade head, the four core tables must exist."""

    def _get_tables(conn):  # type: ignore[no-untyped-def]
        inspector = inspect(conn)
        return inspector.get_table_names()

    async with pg_engine.connect() as conn:
        tables = await conn.run_sync(_get_tables)

    assert "products" in tables
    assert "inventory" in tables
    assert "orders" in tables
    assert "customers" in tables


async def test_inventory_columns_exist(pg_engine: AsyncEngine) -> None:
    """Inventory table has on_hand and reserved integer columns."""

    def _get_columns(conn):  # type: ignore[no-untyped-def]
        inspector = inspect(conn)
        return {col["name"]: col for col in inspector.get_columns("inventory")}

    async with pg_engine.connect() as conn:
        columns = await conn.run_sync(_get_columns)

    assert "on_hand" in columns
    assert "reserved" in columns
    assert columns["on_hand"]["type"].__class__.__name__ == "INTEGER"
    assert columns["reserved"]["type"].__class__.__name__ == "INTEGER"


async def test_inventory_check_constraints_enforced(pg_engine: AsyncEngine) -> None:
    """CHECK constraints on inventory prevent reserved > on_hand and reserved < 0."""
    # Try to insert a row violating on_hand >= reserved
    async with pg_engine.begin() as conn:
        # Seed a valid row first
        await conn.execute(
            text("INSERT INTO inventory (sku, on_hand, reserved) VALUES ('TEST-CHK', 5, 0)")
        )

    # Attempt to violate on_hand >= reserved
    async with pg_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(text("UPDATE inventory SET reserved = 10 WHERE sku = 'TEST-CHK'"))

    # Attempt to violate reserved >= 0
    async with pg_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(text("UPDATE inventory SET reserved = -1 WHERE sku = 'TEST-CHK'"))

    # Clean up
    async with pg_engine.begin() as conn:
        await conn.execute(text("DELETE FROM inventory WHERE sku = 'TEST-CHK'"))


async def test_customers_email_unique_constraint(pg_engine: AsyncEngine) -> None:
    """customers.email has a UNIQUE constraint."""
    async with pg_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO customers (id, email) VALUES ('uuid-c1', 'alice@example.com')")
        )

    # Attempt to insert a duplicate email
    async with pg_engine.begin() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(
                text("INSERT INTO customers (id, email) VALUES ('uuid-c2', 'alice@example.com')")
            )

    # Clean up
    async with pg_engine.begin() as conn:
        await conn.execute(text("DELETE FROM customers WHERE email = 'alice@example.com'"))
