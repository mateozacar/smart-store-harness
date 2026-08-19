"""SQLAlchemy implementation of the ProductRepository port."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.products.entities import SKU, Price, Product
from app.infrastructure.db.models import ProductRow


class SqlAlchemyProductRepository:
    """Adapts ProductRepository port to SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_sku(self, sku: SKU) -> Product | None:
        """Return the Product for the given SKU, or None if not found."""
        stmt = select(ProductRow).where(ProductRow.sku == sku.value)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Product(
            id=row.id,
            sku=SKU(row.sku),
            name=row.name,
            price=Price(Decimal(str(row.price))),
        )

    async def add(self, product: Product) -> None:
        """Persist a new Product to the database."""
        row = ProductRow(
            id=product.id,
            sku=product.sku.value,
            name=product.name,
            price=product.price.value,
        )
        self._session.add(row)
        await self._session.flush()
