"""Unit tests for the PlaceOrder use case.

Test Matrix coverage:
- Order placed with customer attached (unit)
- Anonymous order placed without customer (unit)
- Order rejected when customer does not exist (unit)
- Order rejected when stock insufficient (unit)
"""

from __future__ import annotations

import pytest

from app.application.place_order import PlaceOrderCommand, PlaceOrderUseCase
from app.domain.customers.entities import Customer, Email
from app.domain.errors import CustomerNotFoundError
from app.domain.inventory.entities import InsufficientStockError
from app.domain.orders.entities import OrderStatus
from tests.unit.fakes import FakeUnitOfWork

# ---------------------------------------------------------------------------
# Gherkin scenario: Order placed with customer attached
# ---------------------------------------------------------------------------


async def test_reserves_inventory_and_attaches_customer() -> None:
    """Scenario: Order placed with customer attached.

    A registered customer exists; order is placed with customer_id set.
    Inventory is reserved, order is PENDING with customer_id populated.
    """
    customer = Customer(id="CUST-1", email=Email.normalize("buyer@example.com"))
    uow = FakeUnitOfWork.with_stock(
        {"SKU-A": (10, 0)},
        customers={"CUST-1": customer},
    )
    use_case = PlaceOrderUseCase(uow)

    order = await use_case.execute(PlaceOrderCommand(customer_id="CUST-1", lines=(("SKU-A", 3),)))

    assert order.status == OrderStatus.PENDING
    assert order.customer_id == "CUST-1"
    assert len(order.lines) == 1
    assert order.lines[0].sku.value == "SKU-A"
    assert order.lines[0].quantity == 3

    level = uow.inventory.state["SKU-A"]
    assert level.reserved == 3
    assert level.on_hand == 10
    assert uow.committed is True


# ---------------------------------------------------------------------------
# Gherkin scenario: Anonymous order placed without customer
# ---------------------------------------------------------------------------


async def test_reserves_inventory_without_customer() -> None:
    """Scenario: Anonymous order placed without customer.

    customer_id is None; order is placed successfully with inventory reserved.
    """
    uow = FakeUnitOfWork.with_stock({"SKU-B": (5, 0)})
    use_case = PlaceOrderUseCase(uow)

    order = await use_case.execute(PlaceOrderCommand(customer_id=None, lines=(("SKU-B", 2),)))

    assert order.status == OrderStatus.PENDING
    assert order.customer_id is None
    assert len(order.lines) == 1

    level = uow.inventory.state["SKU-B"]
    assert level.reserved == 2
    assert level.on_hand == 5
    assert uow.committed is True


# ---------------------------------------------------------------------------
# Gherkin scenario: Order rejected when customer does not exist
# ---------------------------------------------------------------------------


async def test_rejects_order_for_unknown_customer() -> None:
    """Scenario: Order rejected when customer does not exist.

    customer_id references a non-existent customer; CustomerNotFoundError is raised.
    No order is placed, no inventory is reserved.
    """
    uow = FakeUnitOfWork.with_stock({"SKU-C": (5, 0)})
    use_case = PlaceOrderUseCase(uow)

    with pytest.raises(CustomerNotFoundError) as exc_info:
        await use_case.execute(PlaceOrderCommand(customer_id="ghost-id", lines=(("SKU-C", 1),)))

    assert exc_info.value.http_status == 422
    assert exc_info.value.customer_id == "ghost-id"
    # No order persisted, no reservation made
    assert len(uow.orders.saved) == 0
    level = uow.inventory.state["SKU-C"]
    assert level.reserved == 0
    assert uow.committed is False


# ---------------------------------------------------------------------------
# Gherkin scenario: Order rejected when stock insufficient
# ---------------------------------------------------------------------------


async def test_rejects_order_when_stock_insufficient() -> None:
    """Scenario: Order rejected when stock insufficient.

    on_hand=2, reserved=1 -> available=1; requesting 2 raises InsufficientStockError.
    No order is persisted.
    """
    uow = FakeUnitOfWork.with_stock({"SKU-D": (2, 1)})
    use_case = PlaceOrderUseCase(uow)

    with pytest.raises(InsufficientStockError) as exc_info:
        await use_case.execute(PlaceOrderCommand(customer_id=None, lines=(("SKU-D", 2),)))

    assert exc_info.value.http_status == 409
    assert exc_info.value.sku == "SKU-D"
    assert exc_info.value.requested == 2
    assert exc_info.value.available == 1
    assert len(uow.orders.saved) == 0
    level = uow.inventory.state["SKU-D"]
    assert level.reserved == 1  # unchanged
    assert uow.committed is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_order_with_multiple_lines_reserves_all() -> None:
    """Multiple lines each reserve their respective SKU."""
    uow = FakeUnitOfWork.with_stock({"SKU-X": (10, 0), "SKU-Y": (5, 2)})
    use_case = PlaceOrderUseCase(uow)

    order = await use_case.execute(
        PlaceOrderCommand(customer_id=None, lines=(("SKU-X", 4), ("SKU-Y", 2)))
    )

    assert len(order.lines) == 2
    assert uow.inventory.state["SKU-X"].reserved == 4
    assert uow.inventory.state["SKU-Y"].reserved == 4  # 2 already + 2 new
    assert uow.committed is True


async def test_partial_failure_does_not_commit() -> None:
    """If second line is insufficient, the UoW is not committed (no partial state)."""
    uow = FakeUnitOfWork.with_stock({"SKU-OK": (10, 0), "SKU-NO": (1, 1)})
    use_case = PlaceOrderUseCase(uow)

    with pytest.raises(InsufficientStockError):
        await use_case.execute(
            PlaceOrderCommand(customer_id=None, lines=(("SKU-OK", 1), ("SKU-NO", 1)))
        )

    assert uow.committed is False
    assert len(uow.orders.saved) == 0


async def test_order_id_is_unique_across_calls() -> None:
    """Two separate orders get distinct IDs."""
    uow1 = FakeUnitOfWork.with_stock({"SKU-Z": (10, 0)})
    uow2 = FakeUnitOfWork.with_stock({"SKU-Z": (10, 0)})
    uc1 = PlaceOrderUseCase(uow1)
    uc2 = PlaceOrderUseCase(uow2)

    o1 = await uc1.execute(PlaceOrderCommand(customer_id=None, lines=(("SKU-Z", 1),)))
    o2 = await uc2.execute(PlaceOrderCommand(customer_id=None, lines=(("SKU-Z", 1),)))

    assert o1.id != o2.id
