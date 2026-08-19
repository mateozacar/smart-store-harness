"""SQLAlchemy implementation of the CustomerRepository port."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.customers.entities import Customer, Email, EmailConflictError
from app.infrastructure.db.models import CustomerRow


class SqlAlchemyCustomerRepository:
    """Adapts CustomerRepository port to SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, customer: Customer) -> None:
        """Persist a new Customer to the database.

        Raises EmailConflictError if a customer with the same email already exists.
        The IntegrityError on uq_customers_email is translated here at the
        repository boundary, keeping infrastructure exceptions out of the domain.
        """
        row = CustomerRow(
            id=customer.id,
            email=customer.email.value,
        )
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._session.rollback()
            if "uq_customers_email" in str(exc.orig):
                raise EmailConflictError(customer.email.value) from exc
            raise

    async def get_by_email(self, email: Email) -> Customer | None:
        """Return the Customer with the given email, or None if not found."""
        stmt = select(CustomerRow).where(CustomerRow.email == email.value)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Customer(id=row.id, email=Email(row.email))

    async def get_by_id(self, customer_id: str) -> Customer | None:
        """Return the Customer with the given id, or None if not found."""
        stmt = select(CustomerRow).where(CustomerRow.id == customer_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Customer(id=row.id, email=Email(row.email))
