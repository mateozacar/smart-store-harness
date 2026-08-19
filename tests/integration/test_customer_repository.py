"""Integration tests: SqlAlchemyCustomerRepository against real Postgres."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.customers.entities import Customer, Email, EmailConflictError
from app.infrastructure.db.repositories.customers import SqlAlchemyCustomerRepository
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _register(
    session_factory: async_sessionmaker[AsyncSession],
    raw_email: str,
) -> Customer:
    """Register a customer using the real UnitOfWork."""
    uow = SqlAlchemyUnitOfWork(session_factory)
    async with uow:
        email = Email.normalize(raw_email)
        customer = Customer(email=email)
        await uow.customers.add(customer)
        await uow.commit()
        return customer


# ---------------------------------------------------------------------------
# Happy-path
# ---------------------------------------------------------------------------


async def test_save_and_retrieve_customer_by_email(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Repository can persist a Customer and retrieve it by email."""
    raw = "repo-test-buyer@example.com"
    await _register(pg_session_factory, raw)

    async with pg_session_factory() as session:
        repo = SqlAlchemyCustomerRepository(session)
        found = await repo.get_by_email(Email.normalize(raw))

    assert found is not None
    assert found.email.value == raw


async def test_get_by_email_returns_none_when_not_found(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Repository returns None for an email that does not exist."""
    async with pg_session_factory() as session:
        repo = SqlAlchemyCustomerRepository(session)
        result = await repo.get_by_email(Email.normalize("ghost@example.com"))

    assert result is None


# ---------------------------------------------------------------------------
# Duplicate email — exact match
# (Test Matrix: "Duplicate email exact match")
# ---------------------------------------------------------------------------


async def test_save_raises_email_conflict_on_duplicate(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Duplicate email exact match is rejected at the DB boundary.

    Inserting a second customer with the same email triggers a unique
    constraint violation, which is translated to EmailConflictError by
    the UnitOfWork commit handler.
    """
    raw = "duplicate-exact@example.com"
    await _register(pg_session_factory, raw)

    with pytest.raises(EmailConflictError) as exc_info:
        await _register(pg_session_factory, raw)

    assert exc_info.value.http_status == 409


# ---------------------------------------------------------------------------
# Duplicate email — different casing
# (Test Matrix: "Duplicate email different casing")
# ---------------------------------------------------------------------------


async def test_save_raises_email_conflict_on_case_insensitive_duplicate(
    pg_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Scenario: Duplicate email with different casing is rejected.

    Since the use case normalizes to lowercase before persistence,
    'original@example.com' and 'ORIGINAL@EXAMPLE.COM' map to the same
    row and trigger the unique constraint.
    """
    raw = "case-insensitive-dup@example.com"
    await _register(pg_session_factory, raw)

    with pytest.raises(EmailConflictError) as exc_info:
        await _register(pg_session_factory, "CASE-INSENSITIVE-DUP@EXAMPLE.COM")

    assert exc_info.value.http_status == 409
