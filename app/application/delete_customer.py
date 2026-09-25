"""DeleteCustomer use case — removes a customer who has no active orders."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import CustomerHasActiveOrdersError, CustomerNotFoundError


@dataclass(frozen=True)
class DeleteCustomerCommand:
    """Input command for the DeleteCustomer use case."""

    customer_id: str


class DeleteCustomerUseCase:
    """Orchestrates customer deletion within a unit of work.

    Raises CustomerNotFoundError if the customer does not exist.
    Raises CustomerHasActiveOrdersError if the customer has any PENDING or
    CONFIRMED orders, which would violate the referential integrity invariant
    stated in PRD §3.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: DeleteCustomerCommand) -> None:
        """Delete the customer, or raise a domain error if not possible."""
        async with self._uow:
            customer = await self._uow.customers.get_by_id(cmd.customer_id)
            if customer is None:
                raise CustomerNotFoundError(cmd.customer_id)

            has_active = await self._uow.orders.has_active_orders_for_customer(cmd.customer_id)
            if has_active:
                raise CustomerHasActiveOrdersError(cmd.customer_id)

            await self._uow.customers.delete(cmd.customer_id)
            await self._uow.commit()
