"""Unit tests for the ListProducts use case."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.application.list_products import ListProductsQuery, ListProductsUseCase
from app.domain.errors import InvalidPaginationError, InvalidPriceRangeError
from app.domain.products.entities import SKU, Price, Product, ProductPage


def _utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


class FakeProductRepository:
    """In-memory product repository for unit testing list behaviour."""

    def __init__(self, products: list[tuple[Product, datetime]]) -> None:
        # Each entry is (product, created_at) — simplest fake that supports ordering
        self._entries = products

    async def get_by_sku(self, sku: SKU) -> Product | None:  # pragma: no cover
        for prod, _ in self._entries:
            if prod.sku == sku:
                return prod
        return None

    async def add(self, product: Product) -> None:  # pragma: no cover
        pass

    async def list(
        self,
        page: int,
        size: int,
        min_price: Price | None,
        max_price: Price | None,
    ) -> ProductPage:
        # Sort by created_at descending and apply optional price filters
        filtered_with_ts = [
            (prod, ts)
            for prod, ts in self._entries
            if (min_price is None or prod.price.value >= min_price.value)
            and (max_price is None or prod.price.value <= max_price.value)
        ]
        filtered_with_ts.sort(key=lambda x: x[1], reverse=True)
        total = len(filtered_with_ts)
        offset = (page - 1) * size
        items = [prod for prod, _ in filtered_with_ts[offset : offset + size]]
        return ProductPage(items=items, total=total, page=page, size=size)


class FakeUnitOfWork:
    """In-memory unit of work for unit testing."""

    def __init__(self, repo: FakeProductRepository) -> None:
        self.products = repo
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Scenario 1: Buyer lists products with default pagination
# ---------------------------------------------------------------------------


async def test_returns_page_ordered_by_created_at_desc() -> None:
    """Products are returned ordered by created_at descending."""
    products = [
        (Product(sku=SKU("SKU-A"), name="A", price=Price(Decimal("10.00"))), _utc(2024, 1, 1)),
        (Product(sku=SKU("SKU-B"), name="B", price=Price(Decimal("20.00"))), _utc(2024, 1, 2)),
        (Product(sku=SKU("SKU-C"), name="C", price=Price(Decimal("30.00"))), _utc(2024, 1, 3)),
    ]
    uow = FakeUnitOfWork(FakeProductRepository(products))
    use_case = ListProductsUseCase(uow)

    page = await use_case.execute(ListProductsQuery(page=1, size=20))

    assert page.total == 3
    assert page.page == 1
    assert page.size == 20
    assert [p.sku.value for p in page.items] == ["SKU-C", "SKU-B", "SKU-A"]


# ---------------------------------------------------------------------------
# Scenario 2: Buyer filters products by price range
# ---------------------------------------------------------------------------


async def test_filters_by_inclusive_price_range() -> None:
    """Only products within [min_price, max_price] are returned."""
    products = [
        (Product(sku=SKU("P-5"), name="5", price=Price(Decimal("5.00"))), _utc(2024, 1, 1)),
        (Product(sku=SKU("P-15"), name="15", price=Price(Decimal("15.00"))), _utc(2024, 1, 2)),
        (Product(sku=SKU("P-25"), name="25", price=Price(Decimal("25.00"))), _utc(2024, 1, 3)),
        (Product(sku=SKU("P-50"), name="50", price=Price(Decimal("50.00"))), _utc(2024, 1, 4)),
    ]
    uow = FakeUnitOfWork(FakeProductRepository(products))
    use_case = ListProductsUseCase(uow)

    page = await use_case.execute(
        ListProductsQuery(page=1, size=20, min_price=Decimal("10"), max_price=Decimal("30"))
    )

    assert page.total == 2
    skus = {p.sku.value for p in page.items}
    assert skus == {"P-15", "P-25"}


# ---------------------------------------------------------------------------
# Scenario 3: Buyer requests a page beyond the last
# ---------------------------------------------------------------------------


async def test_returns_empty_items_when_page_beyond_last() -> None:
    """Empty items list with correct metadata when page exceeds available results."""
    products = [
        (Product(sku=SKU("SKU-A"), name="A", price=Price(Decimal("10.00"))), _utc(2024, 1, 1)),
        (Product(sku=SKU("SKU-B"), name="B", price=Price(Decimal("20.00"))), _utc(2024, 1, 2)),
        (Product(sku=SKU("SKU-C"), name="C", price=Price(Decimal("30.00"))), _utc(2024, 1, 3)),
    ]
    uow = FakeUnitOfWork(FakeProductRepository(products))
    use_case = ListProductsUseCase(uow)

    page = await use_case.execute(ListProductsQuery(page=5, size=20))

    assert list(page.items) == []
    assert page.total == 3
    assert page.page == 5
    assert page.size == 20


# ---------------------------------------------------------------------------
# Scenario 4: Buyer sends an invalid price range
# ---------------------------------------------------------------------------


async def test_rejects_max_below_min_with_invalid_price_range() -> None:
    """InvalidPriceRangeError raised when max_price < min_price."""
    uow = FakeUnitOfWork(FakeProductRepository([]))
    use_case = ListProductsUseCase(uow)

    with pytest.raises(InvalidPriceRangeError):
        await use_case.execute(
            ListProductsQuery(page=1, size=20, min_price=Decimal("50"), max_price=Decimal("10"))
        )


async def test_rejects_negative_min_price() -> None:
    """InvalidPriceRangeError raised when min_price is negative."""
    uow = FakeUnitOfWork(FakeProductRepository([]))
    use_case = ListProductsUseCase(uow)

    with pytest.raises(InvalidPriceRangeError):
        await use_case.execute(ListProductsQuery(page=1, size=20, min_price=Decimal("-1")))


async def test_rejects_invalid_pagination_page_zero() -> None:
    """InvalidPaginationError raised when page < 1."""
    uow = FakeUnitOfWork(FakeProductRepository([]))
    use_case = ListProductsUseCase(uow)

    with pytest.raises(InvalidPaginationError):
        await use_case.execute(ListProductsQuery(page=0, size=20))


async def test_rejects_invalid_pagination_size_too_large() -> None:
    """InvalidPaginationError raised when size > 100."""
    uow = FakeUnitOfWork(FakeProductRepository([]))
    use_case = ListProductsUseCase(uow)

    with pytest.raises(InvalidPaginationError):
        await use_case.execute(ListProductsQuery(page=1, size=101))
