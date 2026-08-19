"""SQLAlchemy implementation of the InventoryRepository port."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DomainError
from app.domain.inventory.entities import InventoryLevel
from app.domain.products.entities import SKU
from app.infrastructure.db.models import InventoryRow


class SqlAlchemyInventoryRepository:
    """Adapts InventoryRepository port to SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_update(self, sku: SKU) -> InventoryLevel:
        """Acquire a row-level lock and return the InventoryLevel for the given SKU.

        Uses SELECT ... FOR UPDATE to serialize concurrent reservations.

        Raises:
            DomainError: if no inventory row exists for the SKU.
        """
        stmt = select(InventoryRow).where(InventoryRow.sku == sku.value).with_for_update()
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise DomainError("inventory-not-found", f"No inventory record for SKU '{sku.value}'.")
        return InventoryLevel(sku=SKU(row.sku), on_hand=row.on_hand, reserved=row.reserved)

    async def save(self, level: InventoryLevel) -> None:
        """Persist updated inventory level back to the database."""
        stmt = select(InventoryRow).where(InventoryRow.sku == level.sku.value)
        row = (await self._session.execute(stmt)).scalar_one()
        row.on_hand = level.on_hand
        row.reserved = level.reserved
