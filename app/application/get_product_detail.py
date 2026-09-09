"""GetProductDetailUseCase — fetches product with its current available stock."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import ProductNotFoundError
from app.domain.products.entities import SKU


@dataclass(frozen=True)
class GetProductDetailQuery:
    """Input for GetProductDetailUseCase."""

    sku: str


@dataclass(frozen=True)
class ProductDetail:
    """Combined view of a product with its current available stock."""

    id: str
    sku: str
    name: str
    price: Decimal
    available: int


class GetProductDetailUseCase:
    """Fetches a product by SKU and its current available stock."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: GetProductDetailQuery) -> ProductDetail:
        """Return ProductDetail for the given SKU.

        Raises:
            ProductNotFoundError: if no product with the given SKU exists.
        """
        async with self._uow:
            sku = SKU(query.sku)
            product = await self._uow.products.get_by_sku(sku)
            if product is None:
                raise ProductNotFoundError(query.sku)
            level = await self._uow.inventory.get(sku)
            available = level.available() if level is not None else 0
            return ProductDetail(
                id=product.id,
                sku=product.sku.value,
                name=product.name,
                price=product.price.value,
                available=available,
            )
