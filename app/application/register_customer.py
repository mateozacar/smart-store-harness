"""RegisterCustomer use case — registers a new customer with a unique email."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.unit_of_work import UnitOfWork
from app.domain.customers.entities import Customer, Email


@dataclass(frozen=True)
class RegisterCustomerCommand:
    """Input command for the RegisterCustomer use case."""

    email: str


class RegisterCustomerUseCase:
    """Orchestrates customer registration within a unit of work."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: RegisterCustomerCommand) -> Customer:
        """Register a customer, raising EmailConflictError if email already exists.

        The raw email is normalized to lowercase before validation and persistence.
        InvalidEmailError is raised if the email does not match RFC 5322 basic form.
        EmailConflictError is raised if a customer with the same normalized email exists.
        """
        email = Email.normalize(cmd.email)
        customer = Customer(email=email)

        async with self._uow:
            await self._uow.customers.add(customer)
            await self._uow.commit()
            return customer
