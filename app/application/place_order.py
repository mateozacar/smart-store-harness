"""PlaceOrder use case — creates an order with inventory reservation."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import CustomerNotFoundError
from app.domain.orders.entities import Order, OrderLine
from app.domain.products.entities import SKU


@dataclass(frozen=True)
class PlaceOrderCommand:
    """Input command for the PlaceOrder use case."""

    customer_id: str | None
    lines: tuple[tuple[str, int], ...]  # (sku_value, quantity) pairs


class PlaceOrderUseCase:
    """Places an order with atomic inventory reservation.

    Within a single database transaction:
    1. Validates customer existence when customer_id is provided.
    2. Acquires row-level locks (SELECT ... FOR UPDATE) on each affected inventory row.
    3. Reserves the requested quantity per line.
    4. Persists the order in PENDING state.

    If any step raises, the UnitOfWork rolls back and no partial state persists.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: PlaceOrderCommand) -> Order:
        """Execute the place-order command, returning the persisted Order.

        Raises:
            CustomerNotFoundError: if customer_id is provided but not found (422).
            InsufficientStockError: if any line quantity exceeds available stock (409).
        """
        async with self._uow:
            if cmd.customer_id is not None:
                customer = await self._uow.customers.get_by_id(cmd.customer_id)
                if customer is None:
                    raise CustomerNotFoundError(cmd.customer_id)

            order = Order.new(customer_id=cmd.customer_id)

            for sku_value, qty in cmd.lines:
                sku = SKU(sku_value)
                level = await self._uow.inventory.get_for_update(sku)
                level.reserve(qty)
                await self._uow.inventory.save(level)
                order.add_line(OrderLine(sku=sku, quantity=qty))

            await self._uow.orders.add(order)
            await self._uow.commit()
            return order
