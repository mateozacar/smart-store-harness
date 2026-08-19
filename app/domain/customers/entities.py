"""Customer domain entities and value objects."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

from app.domain.errors import DomainError

# RFC 5322 basic form: local@domain with reasonable character set.
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

_EMAIL_MAX_LEN = 254


@dataclass(frozen=True, slots=True)
class Email:
    """Value object representing a normalized, validated email address."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > _EMAIL_MAX_LEN:
            raise InvalidEmailError(self.value)
        if not _EMAIL_RE.match(self.value):
            raise InvalidEmailError(self.value)
        # Enforce normalization: value must already be lowercase.
        if self.value != self.value.lower():
            raise InvalidEmailError(self.value)

    @classmethod
    def normalize(cls, raw: str) -> Email:
        """Normalize raw email to lowercase and construct the value object."""
        return cls(raw.lower())


@dataclass
class Customer:
    """Customer aggregate root."""

    email: Email
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class InvalidEmailError(DomainError):
    """Raised when the provided email does not match RFC 5322 basic form."""

    problem_type = "invalid-email"
    http_status = 422

    def __init__(self, email: str) -> None:
        super().__init__("invalid-email", f"'{email}' is not a valid email address.")
        self.email = email


class EmailConflictError(DomainError):
    """Raised when a customer with the same normalized email already exists."""

    problem_type = "email-conflict"
    http_status = 409

    def __init__(self, email: str) -> None:
        super().__init__("email-conflict", f"A customer with email '{email}' already exists.")
        self.email = email
