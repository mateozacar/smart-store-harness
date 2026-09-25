"""SQLAlchemy implementation of the OrderRepository port."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, select
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

    async def has_active_orders_for_customer(self, customer_id: str) -> bool:
        """Return True if the customer has any PENDING or CONFIRMED orders."""
        _active_statuses = ("PENDING", "CONFIRMED")
        stmt = select(
            exists().where(
                OrderRow.customer_id == customer_id,
                OrderRow.status.in_(_active_statuses),
            )
        )
        result = await self._session.execute(stmt)
        return bool(result.scalar())
