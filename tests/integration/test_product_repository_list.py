"""Integration tests: SqlAlchemyProductRepository.list() against real Postgres."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.products.entities import Price
from app.infrastructure.db.models import ProductRow
from app.infrastructure.db.repositories.products import SqlAlchemyProductRepository

pytestmark = pytest.mark.integration


async def _seed_product(
    session_factory: async_sessionmaker[AsyncSession],
    sku: str,
    price: str,
    created_at: datetime,
) -> None:
    """Insert a ProductRow directly for test seeding."""
    async with session_factory() as session:
        row = ProductRow(
            sku=sku,
            name=f"Product {sku}",
            price=Decimal(price),
            created_at=created_at,
        )
        session.add(row)
        await session.commit()


@pytest.fixture()
async def seeded_factory(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    """Seed four products with distinct prices and ordered created_at timestamps."""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    products = [
        ("INT-P5", "5.00", base),
        ("INT-P15", "15.00", base + timedelta(days=1)),
        ("INT-P25", "25.00", base + timedelta(days=2)),
        ("INT-P50", "50.00", base + timedelta(days=3)),
    ]
    for sku, price, ts in products:
        # Only seed if the product does not yet exist (session-scoped container reuses data)
        async with pg_session_factory() as session:
            existing = (
                await session.execute(select(ProductRow).where(ProductRow.sku == sku))
            ).scalar_one_or_none()
            if existing is None:
                row = ProductRow(
                    sku=sku, name=f"Product {sku}", price=Decimal(price), created_at=ts
                )
                session.add(row)
                await session.commit()
    return pg_session_factory


async def test_query_uses_price_bounds_and_order(
    seeded_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Repository list() filters by price bounds using SQL WHERE and orders by created_at DESC."""
    async with seeded_factory() as session:
        repo = SqlAlchemyProductRepository(session)
        page = await repo.list(
            page=1,
            size=20,
            min_price=Price(Decimal("10")),
            max_price=Price(Decimal("30")),
        )

    assert page.total == 2
    skus = {p.sku.value for p in page.items}
    assert skus == {"INT-P15", "INT-P25"}
    # Order within the two items: INT-P25 created later → should appear first
    assert page.items[0].sku.value == "INT-P25"
    assert page.items[1].sku.value == "INT-P15"


async def test_list_returns_all_products_without_filter(
    seeded_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Repository list() returns all products when no price filter is applied."""
    async with seeded_factory() as session:
        repo = SqlAlchemyProductRepository(session)
        page = await repo.list(page=1, size=20, min_price=None, max_price=None)

    # Session-scoped container may contain products from other tests; at least 4 ours are present
    our_skus = {"INT-P5", "INT-P15", "INT-P25", "INT-P50"}
    found_skus = {p.sku.value for p in page.items}
    assert our_skus.issubset(found_skus)


async def test_list_returns_empty_when_page_beyond_last(
    seeded_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Repository list() returns empty items when offset exceeds total rows."""
    async with seeded_factory() as session:
        repo = SqlAlchemyProductRepository(session)
        page = await repo.list(page=999, size=20, min_price=None, max_price=None)

    assert list(page.items) == []
    assert page.page == 999
    assert page.size == 20
