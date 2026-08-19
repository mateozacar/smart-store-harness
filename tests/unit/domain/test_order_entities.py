"""Unit tests for Order aggregate and OrderLine value object."""

from __future__ import annotations

import pytest

from app.domain.errors import DomainError
from app.domain.orders.entities import Order, OrderLine, OrderStatus
from app.domain.products.entities import SKU

# ---------------------------------------------------------------------------
# OrderLine value object
# ---------------------------------------------------------------------------


def test_order_line_valid() -> None:
    line = OrderLine(sku=SKU("SKU-1"), quantity=5)
    assert line.sku.value == "SKU-1"
    assert line.quantity == 5


def test_order_line_raises_for_zero_quantity() -> None:
    with pytest.raises(DomainError):
        OrderLine(sku=SKU("SKU-1"), quantity=0)


def test_order_line_raises_for_negative_quantity() -> None:
    with pytest.raises(DomainError):
        OrderLine(sku=SKU("SKU-1"), quantity=-1)


# ---------------------------------------------------------------------------
# Order aggregate
# ---------------------------------------------------------------------------


def test_order_new_creates_pending_order() -> None:
    order = Order.new()
    assert order.status == OrderStatus.PENDING
    assert order.customer_id is None
    assert order.lines == []


def test_order_new_with_customer_id() -> None:
    order = Order.new(customer_id="CUST-1")
    assert order.customer_id == "CUST-1"


def test_order_add_line_appends_correctly() -> None:
    order = Order.new()
    line = OrderLine(sku=SKU("SKU-A"), quantity=3)
    order.add_line(line)
    assert len(order.lines) == 1
    assert order.lines[0] is line


def test_order_id_is_uuid_format() -> None:
    order = Order.new()
    assert len(order.id) == 36
    assert order.id.count("-") == 4


def test_order_status_enum_values() -> None:
    """All four status values are defined."""
    assert OrderStatus.PENDING.value == "PENDING"
    assert OrderStatus.CONFIRMED.value == "CONFIRMED"
    assert OrderStatus.FULFILLED.value == "FULFILLED"
    assert OrderStatus.CANCELLED.value == "CANCELLED"
