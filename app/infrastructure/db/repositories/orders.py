"""SQLAlchemy implementation of the OrderRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.orders.entities import Order
from app.infrastructure.db.models import OrderLineRow, OrderRow


class SqlAlchemyOrderRepository:
    """Adapts OrderRepository port to SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, order: Order) -> None:
        """Persist a new Order and its lines to the database."""
        row = OrderRow(
            id=order.id,
            customer_id=order.customer_id,
            status=order.status.value,
        )
        self._session.add(row)

        for line in order.lines:
            line_row = OrderLineRow(
                id=str(uuid.uuid4()),
                order_id=order.id,
                sku=line.sku.value,
                quantity=line.quantity,
            )
            self._session.add(line_row)

        await self._session.flush()
