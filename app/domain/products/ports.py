"""Product repository port (Protocol)."""

from __future__ import annotations

from typing import Protocol

from app.domain.products.entities import SKU, Price, Product, ProductPage


class ProductRepository(Protocol):
    """Port for persisting and retrieving Product aggregates."""

    async def get_by_sku(self, sku: SKU) -> Product | None: ...  # pragma: no cover

    async def add(self, product: Product) -> None: ...  # pragma: no cover

    async def list(
        self,
        page: int,
        size: int,
        min_price: Price | None,
        max_price: Price | None,
    ) -> ProductPage: ...  # pragma: no cover
