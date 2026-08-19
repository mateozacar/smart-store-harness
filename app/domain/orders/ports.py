"""Order repository port (Protocol)."""

from __future__ import annotations

from typing import Protocol

from app.domain.orders.entities import Order


class OrderRepository(Protocol):
    """Port for persisting Order aggregates."""

    async def add(self, order: Order) -> None: ...  # pragma: no cover
