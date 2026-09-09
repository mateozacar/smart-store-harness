"""Unit tests for the GetProductDetailUseCase."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.get_product_detail import GetProductDetailQuery, GetProductDetailUseCase
from app.domain.errors import ProductNotFoundError
from app.domain.inventory.entities import InventoryLevel
from app.domain.products.entities import SKU, Price, Product


class FakeProductRepository:
    def __init__(self, products: dict[str, Product] | None = None) -> None:
        self._products: dict[str, Product] = products or {}

    async def get_by_sku(self, sku: SKU) -> Product | None:
        return self._products.get(sku.value)

    async def add(self, product: Product) -> None:
        self._products[product.sku.value] = product


class FakeInventoryRepository:
    def __init__(self, stock: dict[str, InventoryLevel] | None = None) -> None:
        self._stock: dict[str, InventoryLevel] = stock or {}

    async def get(self, sku: SKU) -> InventoryLevel | None:
        return self._stock.get(sku.value)

    async def get_for_update(self, sku: SKU) -> InventoryLevel:  # pragma: no cover
        raise NotImplementedError

    async def save(self, level: InventoryLevel) -> None:  # pragma: no cover
        raise NotImplementedError


class FakeUnitOfWork:
    def __init__(
        self,
        products: FakeProductRepository | None = None,
        inventory: FakeInventoryRepository | None = None,
    ) -> None:
        self.products = products or FakeProductRepository()
        self.inventory = inventory or FakeInventoryRepository()
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


def _make_product(sku: str = "WIDGET-01", name: str = "Widget", price: str = "9.99") -> Product:
    return Product(sku=SKU(sku), name=name, price=Price(Decimal(price)))


async def test_returns_product_with_available_stock() -> None:
    """Scenario: Product detail returned with available stock."""
    product = _make_product("WIDGET-01", "Widget", "9.99")
    inv = InventoryLevel(sku=SKU("WIDGET-01"), on_hand=10, reserved=3)
    uow = FakeUnitOfWork(
        products=FakeProductRepository({"WIDGET-01": product}),
        inventory=FakeInventoryRepository({"WIDGET-01": inv}),
    )

    result = await GetProductDetailUseCase(uow).execute(GetProductDetailQuery(sku="WIDGET-01"))

    assert result.sku == "WIDGET-01"
    assert result.name == "Widget"
    assert result.price == Decimal("9.99")
    assert result.available == 7


async def test_returns_zero_available_when_no_inventory_row() -> None:
    """Scenario: Product with no inventory row returns available=0."""
    product = _make_product("WIDGET-02")
    uow = FakeUnitOfWork(
        products=FakeProductRepository({"WIDGET-02": product}),
        inventory=FakeInventoryRepository(),
    )

    result = await GetProductDetailUseCase(uow).execute(GetProductDetailQuery(sku="WIDGET-02"))

    assert result.available == 0


async def test_raises_product_not_found_for_unknown_sku() -> None:
    """Scenario: Unknown SKU returns ProductNotFoundError."""
    uow = FakeUnitOfWork()

    with pytest.raises(ProductNotFoundError) as exc_info:
        await GetProductDetailUseCase(uow).execute(GetProductDetailQuery(sku="GHOST-01"))

    assert exc_info.value.sku == "GHOST-01"
    assert exc_info.value.http_status == 404


async def test_product_detail_includes_id() -> None:
    """Happy path: returned detail includes product id."""
    product = _make_product("WIDGET-03")
    uow = FakeUnitOfWork(
        products=FakeProductRepository({"WIDGET-03": product}),
        inventory=FakeInventoryRepository(),
    )

    result = await GetProductDetailUseCase(uow).execute(GetProductDetailQuery(sku="WIDGET-03"))

    assert result.id == product.id


async def test_available_uses_on_hand_minus_reserved() -> None:
    """Edge case: available is strictly on_hand - reserved."""
    product = _make_product("WIDGET-04")
    inv = InventoryLevel(sku=SKU("WIDGET-04"), on_hand=5, reserved=5)
    uow = FakeUnitOfWork(
        products=FakeProductRepository({"WIDGET-04": product}),
        inventory=FakeInventoryRepository({"WIDGET-04": inv}),
    )

    result = await GetProductDetailUseCase(uow).execute(GetProductDetailQuery(sku="WIDGET-04"))

    assert result.available == 0
