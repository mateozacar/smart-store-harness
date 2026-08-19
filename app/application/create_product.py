"""CreateProduct use case — creates a new product in the catalog."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import SkuConflictError
from app.domain.products.entities import SKU, Price, Product


@dataclass(frozen=True)
class CreateProductCommand:
    """Input command for the CreateProduct use case."""

    sku: str
    name: str
    price: Decimal


class CreateProductUseCase:
    """Orchestrates product creation within a unit of work."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: CreateProductCommand) -> Product:
        """Create a product, raising SkuConflictError if the SKU already exists."""
        sku = SKU(cmd.sku)
        price = Price(cmd.price)

        async with self._uow:
            existing = await self._uow.products.get_by_sku(sku)
            if existing is not None:
                raise SkuConflictError(sku.value)
            product = Product(sku=sku, name=cmd.name, price=price)
            await self._uow.products.add(product)
            await self._uow.commit()
            return product
