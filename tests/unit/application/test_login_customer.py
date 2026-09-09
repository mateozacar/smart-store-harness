"""Unit tests for the LoginCustomer use case."""

from __future__ import annotations

import bcrypt
import jwt
import pytest

from app.application.login_customer import LoginCommand, LoginUseCase
from app.domain.customers.entities import Customer, Email
from app.domain.errors import InvalidCredentialsError
from tests.unit.fakes import FakeCustomerRepository, FakeUnitOfWork

_SECRET = "test-secret"
_EXPIRE_MINUTES = 30


def _make_uow_with_customer(email: str, password: str) -> FakeUnitOfWork:
    """Build a FakeUnitOfWork with a single registered customer."""
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    customer = Customer(
        email=Email.normalize(email),
        password_hash=password_hash,
    )
    repo = FakeCustomerRepository({customer.id: customer})
    return FakeUnitOfWork(customers=repo)


# ---------------------------------------------------------------------------
# Scenario: Successful login returns access token
# ---------------------------------------------------------------------------


async def test_successful_login_returns_token() -> None:
    """Scenario: Correct credentials produce a JWT with sub and exp claims."""
    uow = _make_uow_with_customer("ada@example.com", "correct-horse")
    use_case = LoginUseCase(uow, secret_key=_SECRET, token_expire_minutes=_EXPIRE_MINUTES)

    result = await use_case.execute(LoginCommand(email="ada@example.com", password="correct-horse"))

    assert result.token_type == "bearer"
    decoded = jwt.decode(result.access_token, _SECRET, algorithms=["HS256"])
    assert "sub" in decoded
    assert "exp" in decoded


async def test_token_sub_equals_customer_id() -> None:
    """The JWT 'sub' claim must equal the registered customer's id."""
    uow = _make_uow_with_customer("ada@example.com", "correct-horse")
    # Retrieve the customer id that was registered
    customer_id = next(iter(uow.customers._by_id.keys()))

    use_case = LoginUseCase(uow, secret_key=_SECRET, token_expire_minutes=_EXPIRE_MINUTES)
    result = await use_case.execute(LoginCommand(email="ada@example.com", password="correct-horse"))

    decoded = jwt.decode(result.access_token, _SECRET, algorithms=["HS256"])
    assert decoded["sub"] == customer_id


async def test_email_lookup_is_case_insensitive() -> None:
    """Login with uppercase email succeeds when lowercase was registered."""
    uow = _make_uow_with_customer("ada@example.com", "correct-horse")
    use_case = LoginUseCase(uow, secret_key=_SECRET, token_expire_minutes=_EXPIRE_MINUTES)

    result = await use_case.execute(LoginCommand(email="ADA@EXAMPLE.COM", password="correct-horse"))

    assert result.token_type == "bearer"


# ---------------------------------------------------------------------------
# Scenario: Login with wrong password is rejected
# ---------------------------------------------------------------------------


async def test_wrong_password_raises_invalid_credentials() -> None:
    """Scenario: Wrong password raises InvalidCredentialsError (401)."""
    uow = _make_uow_with_customer("ada@example.com", "correct-horse")
    use_case = LoginUseCase(uow, secret_key=_SECRET, token_expire_minutes=_EXPIRE_MINUTES)

    with pytest.raises(InvalidCredentialsError) as exc_info:
        await use_case.execute(LoginCommand(email="ada@example.com", password="wrong-horse"))

    assert exc_info.value.http_status == 401


# ---------------------------------------------------------------------------
# Scenario: Login with unknown email is rejected (no user enumeration)
# ---------------------------------------------------------------------------


async def test_unknown_email_raises_invalid_credentials() -> None:
    """Scenario: Unknown email raises the same InvalidCredentialsError as wrong password."""
    uow = FakeUnitOfWork()  # empty — no customers
    use_case = LoginUseCase(uow, secret_key=_SECRET, token_expire_minutes=_EXPIRE_MINUTES)

    with pytest.raises(InvalidCredentialsError) as exc_info:
        await use_case.execute(LoginCommand(email="ghost@example.com", password="anything"))

    assert exc_info.value.http_status == 401


async def test_unknown_email_and_wrong_password_produce_identical_error() -> None:
    """No-user-enumeration: InvalidCredentialsError fields are the same in both cases."""
    uow_with_customer = _make_uow_with_customer("ada@example.com", "correct-horse")
    uow_empty = FakeUnitOfWork()

    use_case_with = LoginUseCase(uow_with_customer, _SECRET, _EXPIRE_MINUTES)
    use_case_empty = LoginUseCase(uow_empty, _SECRET, _EXPIRE_MINUTES)

    with pytest.raises(InvalidCredentialsError) as exc_wrong_pw:
        await use_case_with.execute(LoginCommand(email="ada@example.com", password="wrong"))

    with pytest.raises(InvalidCredentialsError) as exc_no_user:
        await use_case_empty.execute(LoginCommand(email="ghost@example.com", password="anything"))

    # Same type, code, detail, and HTTP status — no distinguishable difference
    assert exc_wrong_pw.value.problem_type == exc_no_user.value.problem_type
    assert exc_wrong_pw.value.detail == exc_no_user.value.detail
    assert exc_wrong_pw.value.http_status == exc_no_user.value.http_status


async def test_customer_without_password_hash_raises_invalid_credentials() -> None:
    """Customer with no stored hash (pre-auth registration) cannot authenticate."""
    customer = Customer(email=Email.normalize("old@example.com"), password_hash=None)
    repo = FakeCustomerRepository({customer.id: customer})
    uow = FakeUnitOfWork(customers=repo)
    use_case = LoginUseCase(uow, secret_key=_SECRET, token_expire_minutes=_EXPIRE_MINUTES)

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(LoginCommand(email="old@example.com", password="anything"))
