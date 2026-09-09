"""Inventory repository port (Protocol)."""

from __future__ import annotations

from typing import Protocol

from app.domain.inventory.entities import InventoryLevel
from app.domain.products.entities import SKU


class InventoryRepository(Protocol):
    """Port for reading and persisting InventoryLevel aggregates."""

    async def get(self, sku: SKU) -> InventoryLevel | None: ...  # pragma: no cover

    async def get_for_update(self, sku: SKU) -> InventoryLevel: ...  # pragma: no cover

    async def save(self, level: InventoryLevel) -> None: ...  # pragma: no cover
