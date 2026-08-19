"""Unit tests for the CreateProduct use case."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.create_product import CreateProductCommand, CreateProductUseCase
from app.domain.errors import DomainError, SkuConflictError
from app.domain.products.entities import SKU, Price, Product


class FakeProductRepository:
    """In-memory product repository for unit testing."""

    def __init__(self, products: dict[str, Product] | None = None) -> None:
        self._products: dict[str, Product] = products or {}

    async def get_by_sku(self, sku: SKU) -> Product | None:
        return self._products.get(sku.value)

    async def add(self, product: Product) -> None:
        self._products[product.sku.value] = product


class FakeUnitOfWork:
    """In-memory unit of work for unit testing."""

    def __init__(self, repo: FakeProductRepository | None = None) -> None:
        self.products: FakeProductRepository = repo or FakeProductRepository()
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


async def test_creates_product_when_sku_is_new() -> None:
    """Scenario: Product is created when no product with the given SKU exists."""
    uow = FakeUnitOfWork()
    use_case = CreateProductUseCase(uow)

    product = await use_case.execute(
        CreateProductCommand(sku="WIDGET-01", name="Blue Widget", price=Decimal("19.99"))
    )

    assert product.sku.value == "WIDGET-01"
    assert product.name == "Blue Widget"
    assert product.price.value == Decimal("19.99")
    assert uow.committed is True
    assert uow.products._products["WIDGET-01"] is product


async def test_creates_product_with_zero_price() -> None:
    """Scenario: Product with price=0 satisfies the non-negative invariant."""
    uow = FakeUnitOfWork()
    use_case = CreateProductUseCase(uow)

    product = await use_case.execute(
        CreateProductCommand(sku="FREE-SAMPLE", name="Free Sample", price=Decimal("0.00"))
    )

    assert product.price.value == Decimal("0.00")
    assert uow.committed is True


async def test_raises_sku_conflict_when_sku_already_exists() -> None:
    """Scenario: SkuConflictError is raised when a product with the given SKU exists."""
    existing = Product(sku=SKU("SKU-DUP"), name="Original", price=Price(Decimal("10.00")))
    repo = FakeProductRepository({"SKU-DUP": existing})
    uow = FakeUnitOfWork(repo)
    use_case = CreateProductUseCase(uow)

    with pytest.raises(SkuConflictError) as exc_info:
        await use_case.execute(
            CreateProductCommand(sku="SKU-DUP", name="Duplicate", price=Decimal("20.00"))
        )

    assert exc_info.value.sku == "SKU-DUP"
    assert uow.committed is False


async def test_raises_domain_error_for_negative_price() -> None:
    """Scenario: DomainError is raised when price is negative."""
    uow = FakeUnitOfWork()
    use_case = CreateProductUseCase(uow)

    with pytest.raises(DomainError) as exc_info:
        await use_case.execute(
            CreateProductCommand(sku="NEG-PRICE", name="Bad", price=Decimal("-5.00"))
        )

    assert exc_info.value.code == "price-invalid"
    assert uow.committed is False
