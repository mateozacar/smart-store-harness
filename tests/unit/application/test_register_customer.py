"""Unit tests for the RegisterCustomer use case."""

from __future__ import annotations

import pytest

from app.application.register_customer import RegisterCustomerCommand, RegisterCustomerUseCase
from app.domain.customers.entities import Customer, Email, EmailConflictError, InvalidEmailError


class FakeCustomerRepository:
    """In-memory customer repository for unit testing."""

    def __init__(self, customers: dict[str, Customer] | None = None) -> None:
        self._customers: dict[str, Customer] = customers or {}

    async def add(self, customer: Customer) -> None:
        email_value = customer.email.value
        if email_value in self._customers:
            raise EmailConflictError(email_value)
        self._customers[email_value] = customer

    async def get_by_email(self, email: Email) -> Customer | None:
        return self._customers.get(email.value)


class FakeUnitOfWork:
    """In-memory unit of work for unit testing."""

    def __init__(self, repo: FakeCustomerRepository | None = None) -> None:
        self.customers: FakeCustomerRepository = repo or FakeCustomerRepository()
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Happy-path scenarios
# ---------------------------------------------------------------------------


async def test_creates_customer_with_normalized_email() -> None:
    """Scenario: Register customer with a valid new email.

    Use case creates a Customer with normalized email and commits.
    """
    uow = FakeUnitOfWork()
    use_case = RegisterCustomerUseCase(uow)

    customer = await use_case.execute(RegisterCustomerCommand(email="buyer@example.com"))

    assert customer.email.value == "buyer@example.com"
    assert len(customer.id) == 36
    assert uow.committed is True
    assert uow.customers._customers["buyer@example.com"] is customer


async def test_email_is_normalized_to_lowercase_by_use_case() -> None:
    """Scenario: Email with uppercase letters is normalized to lowercase.

    Use case normalizes the raw email before creating the Customer.
    """
    uow = FakeUnitOfWork()
    use_case = RegisterCustomerUseCase(uow)

    customer = await use_case.execute(RegisterCustomerCommand(email="Alice@Example.COM"))

    assert customer.email.value == "alice@example.com"
    assert uow.committed is True
    assert "alice@example.com" in uow.customers._customers


# ---------------------------------------------------------------------------
# Conflict scenarios
# (Test Matrix: "Duplicate email exact match", "Duplicate email different casing")
# ---------------------------------------------------------------------------


async def test_raises_email_conflict_on_duplicate() -> None:
    """Scenario: Duplicate email exact match is rejected.

    Use case raises EmailConflictError when email already exists.
    """
    existing = Customer(email=Email.normalize("taken@example.com"))
    repo = FakeCustomerRepository({"taken@example.com": existing})
    uow = FakeUnitOfWork(repo)
    use_case = RegisterCustomerUseCase(uow)

    with pytest.raises(EmailConflictError) as exc_info:
        await use_case.execute(RegisterCustomerCommand(email="taken@example.com"))

    assert exc_info.value.http_status == 409
    assert uow.committed is False


async def test_raises_email_conflict_on_case_insensitive_duplicate() -> None:
    """Scenario: Duplicate email with different casing is rejected.

    The raw email is normalized before checking for duplicates, so
    'TAKEN@EXAMPLE.COM' collides with 'taken@example.com'.
    """
    existing = Customer(email=Email.normalize("taken@example.com"))
    repo = FakeCustomerRepository({"taken@example.com": existing})
    uow = FakeUnitOfWork(repo)
    use_case = RegisterCustomerUseCase(uow)

    with pytest.raises(EmailConflictError) as exc_info:
        await use_case.execute(RegisterCustomerCommand(email="TAKEN@EXAMPLE.COM"))

    assert exc_info.value.http_status == 409
    assert uow.committed is False


# ---------------------------------------------------------------------------
# Validation failure scenario
# (Test Matrix: "Malformed email")
# ---------------------------------------------------------------------------


async def test_raises_invalid_email_for_malformed_email() -> None:
    """Scenario: Malformed email is rejected with InvalidEmailError.

    The error is raised before any repository interaction.
    """
    uow = FakeUnitOfWork()
    use_case = RegisterCustomerUseCase(uow)

    with pytest.raises(InvalidEmailError) as exc_info:
        await use_case.execute(RegisterCustomerCommand(email="not-an-email"))

    assert exc_info.value.http_status == 422
    assert uow.committed is False
    assert len(uow.customers._customers) == 0
