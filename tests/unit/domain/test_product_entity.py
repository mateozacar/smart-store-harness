"""Unit tests for the Product domain entity and value objects."""

from decimal import Decimal

import pytest

from app.domain.errors import DomainError
from app.domain.products.entities import SKU, Price, Product


def test_product_created_with_valid_fields() -> None:
    """A Product can be constructed with a valid SKU, name, and non-negative price."""
    product = Product(sku=SKU("WIDGET-01"), name="Blue Widget", price=Price(Decimal("19.99")))
    assert product.sku.value == "WIDGET-01"
    assert product.name == "Blue Widget"
    assert product.price.value == Decimal("19.99")


def test_product_with_zero_price_is_accepted() -> None:
    """A Product with price=0 satisfies the non-negative invariant."""
    product = Product(sku=SKU("FREE-SAMPLE"), name="Free Sample", price=Price(Decimal("0.00")))
    assert product.price.value == Decimal("0.00")


def test_price_rejects_negative_value() -> None:
    """Price raises DomainError when the value is negative."""
    with pytest.raises(DomainError) as exc_info:
        Price(Decimal("-5.00"))
    assert exc_info.value.code == "price-invalid"


def test_sku_rejects_empty_string() -> None:
    """SKU raises DomainError when empty."""
    with pytest.raises(DomainError) as exc_info:
        SKU("")
    assert exc_info.value.code == "sku-invalid"


def test_sku_rejects_too_long_value() -> None:
    """SKU raises DomainError when more than 32 characters."""
    with pytest.raises(DomainError) as exc_info:
        SKU("A" * 33)
    assert exc_info.value.code == "sku-invalid"


def test_sku_rejects_non_alphanumeric_with_dashes() -> None:
    """SKU raises DomainError for characters outside alphanumeric-with-dashes set."""
    with pytest.raises(DomainError) as exc_info:
        SKU("INVALID SKU!")
    assert exc_info.value.code == "sku-invalid"


def test_sku_accepts_alphanumeric_with_dashes() -> None:
    """SKU accepts alphanumeric characters and dashes."""
    sku = SKU("MY-PRODUCT-01")
    assert sku.value == "MY-PRODUCT-01"
