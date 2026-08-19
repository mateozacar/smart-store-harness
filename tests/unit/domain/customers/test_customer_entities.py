"""Unit tests for the Customer domain entities and value objects."""

from __future__ import annotations

import pytest

from app.domain.customers.entities import Customer, Email, EmailConflictError, InvalidEmailError

# ---------------------------------------------------------------------------
# Email value object — normalization (Test Matrix: "Email normalized to lowercase")
# ---------------------------------------------------------------------------


def test_email_value_object_normalizes_to_lowercase() -> None:
    """Scenario: Email value object normalizes uppercase input to lowercase."""
    email = Email.normalize("Alice@Example.COM")
    assert email.value == "alice@example.com"


def test_email_value_object_accepts_already_lowercase() -> None:
    """Email.normalize passes through an already-lowercase address."""
    email = Email.normalize("buyer@example.com")
    assert email.value == "buyer@example.com"


def test_email_value_object_rejects_uppercase_direct_construction() -> None:
    """Email.__init__ rejects a non-normalized (uppercase) value directly."""
    with pytest.raises(InvalidEmailError) as exc_info:
        Email("Alice@Example.COM")
    assert exc_info.value.http_status == 422


# ---------------------------------------------------------------------------
# Email value object — RFC 5322 basic form validation
# (Test Matrix: "Malformed email")
# ---------------------------------------------------------------------------


def test_email_value_object_raises_invalid_email_on_bad_format() -> None:
    """Scenario: Malformed email raises InvalidEmailError."""
    with pytest.raises(InvalidEmailError) as exc_info:
        Email.normalize("not-an-email")
    assert exc_info.value.problem_type == "invalid-email"
    assert exc_info.value.http_status == 422


def test_email_value_object_rejects_missing_at_sign() -> None:
    """Email without '@' is rejected."""
    with pytest.raises(InvalidEmailError):
        Email.normalize("noatsign.com")


def test_email_value_object_rejects_missing_domain() -> None:
    """Email without domain is rejected."""
    with pytest.raises(InvalidEmailError):
        Email.normalize("local@")


def test_email_value_object_rejects_empty_string() -> None:
    """Empty string raises InvalidEmailError."""
    with pytest.raises(InvalidEmailError):
        Email.normalize("")


def test_email_value_object_rejects_missing_tld() -> None:
    """Email without TLD (no dot in domain) is rejected."""
    with pytest.raises(InvalidEmailError):
        Email.normalize("user@nodot")


def test_email_value_object_accepts_valid_formats() -> None:
    """Various valid RFC 5322 basic-form emails are accepted."""
    valid_emails = [
        "user@example.com",
        "user.name+tag@example.co.uk",
        "user123@sub.domain.org",
        "user_name@example.io",
    ]
    for raw in valid_emails:
        email = Email.normalize(raw)
        assert email.value == raw.lower()


# ---------------------------------------------------------------------------
# Customer aggregate
# ---------------------------------------------------------------------------


def test_customer_has_auto_generated_id() -> None:
    """Customer is created with a UUID id when none is provided."""
    customer = Customer(email=Email.normalize("buyer@example.com"))
    assert len(customer.id) == 36
    assert customer.id.count("-") == 4


def test_two_customers_have_different_ids() -> None:
    """Two Customer instances have distinct ids."""
    c1 = Customer(email=Email.normalize("a@example.com"))
    c2 = Customer(email=Email.normalize("b@example.com"))
    assert c1.id != c2.id


# ---------------------------------------------------------------------------
# Domain error classes
# ---------------------------------------------------------------------------


def test_email_conflict_error_has_correct_status() -> None:
    """EmailConflictError has http_status 409 and correct problem_type."""
    err = EmailConflictError("taken@example.com")
    assert err.http_status == 409
    assert err.problem_type == "email-conflict"
    assert "taken@example.com" in err.detail


def test_invalid_email_error_has_correct_status() -> None:
    """InvalidEmailError has http_status 422 and correct problem_type."""
    err = InvalidEmailError("bad-email")
    assert err.http_status == 422
    assert err.problem_type == "invalid-email"
