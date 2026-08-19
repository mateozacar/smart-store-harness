"""Customer repository port (Protocol)."""

from __future__ import annotations

from typing import Protocol

from app.domain.customers.entities import Customer, Email


class CustomerRepository(Protocol):
    """Port for persisting and retrieving Customer aggregates."""

    async def add(self, customer: Customer) -> None: ...  # pragma: no cover

    async def get_by_email(self, email: Email) -> Customer | None: ...  # pragma: no cover
