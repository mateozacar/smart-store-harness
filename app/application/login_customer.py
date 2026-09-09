"""LoginCustomer use case — authenticate a buyer and issue a JWT access token."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.application.unit_of_work import UnitOfWork
from app.domain.customers.entities import Email
from app.domain.errors import InvalidCredentialsError


@dataclass(frozen=True)
class LoginCommand:
    """Input command for the LoginCustomer use case."""

    email: str
    password: str


@dataclass(frozen=True)
class TokenResult:
    """Output from a successful login."""

    access_token: str
    token_type: str = "bearer"


class LoginUseCase:
    """Authenticate a Buyer and return a short-lived JWT access token.

    The secret_key and token_expire_minutes are injected at construction time
    so that the application layer does not import from infrastructure.
    """

    def __init__(self, uow: UnitOfWork, secret_key: str, token_expire_minutes: int) -> None:
        self._uow = uow
        self._secret_key = secret_key
        self._token_expire_minutes = token_expire_minutes

    async def execute(self, cmd: LoginCommand) -> TokenResult:
        """Verify credentials and return a JWT.

        Raises InvalidCredentialsError for any failure — unknown email, wrong
        password, or customer without a stored hash — so callers cannot
        distinguish the failure mode and enumerate registered emails.
        """
        email = Email.normalize(cmd.email)

        async with self._uow:
            customer = await self._uow.customers.get_by_email(email)

        # Unified error path: treat missing customer the same as wrong password.
        if customer is None or customer.password_hash is None:
            raise InvalidCredentialsError()

        stored_hash = customer.password_hash.encode()
        if not bcrypt.checkpw(cmd.password.encode(), stored_hash):
            raise InvalidCredentialsError()

        expiry = datetime.now(UTC) + timedelta(minutes=self._token_expire_minutes)
        payload: dict[str, object] = {"sub": customer.id, "exp": expiry}
        token = jwt.encode(payload, self._secret_key, algorithm="HS256")
        return TokenResult(access_token=token)
