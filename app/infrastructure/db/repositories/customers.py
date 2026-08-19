"""SQLAlchemy implementation of the CustomerRepository port."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.customers.entities import Customer, Email
from app.infrastructure.db.models import CustomerRow


class SqlAlchemyCustomerRepository:
    """Adapts CustomerRepository port to SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, customer: Customer) -> None:
        """Persist a new Customer to the database."""
        row = CustomerRow(
            id=customer.id,
            email=customer.email.value,
        )
        self._session.add(row)
        await self._session.flush()

    async def get_by_email(self, email: Email) -> Customer | None:
        """Return the Customer with the given email, or None if not found."""
        stmt = select(CustomerRow).where(CustomerRow.email == email.value)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        return Customer(id=row.id, email=Email(row.email))
