"""Unit tests for domain error hierarchy."""

import pytest

from app.domain.errors import DomainError


def test_domain_error_stores_code_and_detail() -> None:
    """DomainError records the error code and detail message."""
    err = DomainError("test-code", "Something went wrong")
    assert err.code == "test-code"
    assert err.detail == "Something went wrong"
    assert str(err) == "Something went wrong"


def test_domain_error_default_problem_type() -> None:
    """DomainError has a default problem_type and http_status."""
    err = DomainError("test-code", "detail")
    assert err.problem_type == "domain-error"
    assert err.http_status == 422


def test_domain_error_is_exception() -> None:
    """DomainError can be raised and caught."""
    with pytest.raises(DomainError) as exc_info:
        raise DomainError("err-code", "Error detail")

    assert exc_info.value.code == "err-code"
    assert exc_info.value.detail == "Error detail"
