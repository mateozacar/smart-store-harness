"""SQLAlchemy implementation of the ProductRepository port."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.products.entities import SKU, Price, Product, ProductPage
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

    async def list(
        self,
        page: int,
        size: int,
        min_price: Price | None,
        max_price: Price | None,
    ) -> ProductPage:
        """Return a paginated, optionally price-filtered page of products."""
        base = select(ProductRow)
        if min_price is not None:
            base = base.where(ProductRow.price >= min_price.value)
        if max_price is not None:
            base = base.where(ProductRow.price <= max_price.value)

        count_stmt = select(func.count()).select_from(base.subquery())
        total: int = (await self._session.execute(count_stmt)).scalar_one()

        items_stmt = (
            base.order_by(ProductRow.created_at.desc()).offset((page - 1) * size).limit(size)
        )
        rows = (await self._session.execute(items_stmt)).scalars().all()
        items = [
            Product(
                id=row.id,
                sku=SKU(row.sku),
                name=row.name,
                price=Price(Decimal(str(row.price))),
            )
            for row in rows
        ]
        return ProductPage(items=items, total=total, page=page, size=size)
