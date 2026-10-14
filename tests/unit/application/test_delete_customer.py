"""Unit tests for the DeleteCustomer use case."""

from __future__ import annotations

import pytest

from app.application.delete_customer import DeleteCustomerCommand, DeleteCustomerUseCase
from app.domain.customers.entities import Customer, Email
from app.domain.errors import CustomerDeleteNotFoundError, CustomerHasActiveOrdersError
from app.domain.orders.entities import Order, OrderStatus
from tests.unit.fakes import (
    FakeCustomerRepository,
    FakeOrderRepository,
    FakeUnitOfWork,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_customer(email: str = "buyer@example.com", cid: str = "cust-1") -> Customer:
    return Customer(email=Email.normalize(email), id=cid)


def _make_order(
    customer_id: str,
    status: OrderStatus = OrderStatus.PENDING,
    order_id: str = "order-1",
) -> Order:
    return Order(id=order_id, status=status, lines=[], customer_id=customer_id)


# ---------------------------------------------------------------------------
# Scenario: Successful customer deletion
# ---------------------------------------------------------------------------


async def test_delete_customer_removes_customer_and_commits() -> None:
    """Scenario: Successful customer deletion removes the row and commits."""
    customer = _make_customer()
    customer_repo = FakeCustomerRepository({"cust-1": customer})
    order_repo = FakeOrderRepository()
    uow = FakeUnitOfWork(customers=customer_repo, orders=order_repo)
    use_case = DeleteCustomerUseCase(uow)

    await use_case.execute(DeleteCustomerCommand(customer_id="cust-1"))

    assert uow.committed is True
    assert await customer_repo.get_by_id("cust-1") is None


# ---------------------------------------------------------------------------
# Scenario: Delete non-existent customer returns 404
# ---------------------------------------------------------------------------


async def test_delete_raises_not_found_for_missing_customer() -> None:
    """Scenario: Deleting a non-existent customer raises CustomerNotFoundError."""
    uow = FakeUnitOfWork()
    use_case = DeleteCustomerUseCase(uow)

    with pytest.raises(CustomerDeleteNotFoundError) as exc_info:
        await use_case.execute(DeleteCustomerCommand(customer_id="uuid-99"))

    assert exc_info.value.http_status == 404
    assert exc_info.value.problem_type == "customer-not-found"
    assert uow.committed is False


# ---------------------------------------------------------------------------
# Scenario: Delete customer with active orders is rejected
# ---------------------------------------------------------------------------


async def test_delete_raises_has_active_orders_when_pending_order_exists() -> None:
    """Scenario: Customer with a PENDING order cannot be deleted."""
    customer = _make_customer()
    order = _make_order(customer_id="cust-1", status=OrderStatus.PENDING)
    customer_repo = FakeCustomerRepository({"cust-1": customer})
    order_repo = FakeOrderRepository(orders=[order])
    uow = FakeUnitOfWork(customers=customer_repo, orders=order_repo)
    use_case = DeleteCustomerUseCase(uow)

    with pytest.raises(CustomerHasActiveOrdersError) as exc_info:
        await use_case.execute(DeleteCustomerCommand(customer_id="cust-1"))

    assert exc_info.value.http_status == 409
    assert exc_info.value.problem_type == "customer-has-active-orders"
    assert uow.committed is False
    # Customer row must still exist
    assert await customer_repo.get_by_id("cust-1") is not None


async def test_delete_raises_has_active_orders_when_confirmed_order_exists() -> None:
    """Customer with a CONFIRMED order cannot be deleted."""
    customer = _make_customer()
    order = _make_order(customer_id="cust-1", status=OrderStatus.CONFIRMED)
    customer_repo = FakeCustomerRepository({"cust-1": customer})
    order_repo = FakeOrderRepository(orders=[order])
    uow = FakeUnitOfWork(customers=customer_repo, orders=order_repo)
    use_case = DeleteCustomerUseCase(uow)

    with pytest.raises(CustomerHasActiveOrdersError):
        await use_case.execute(DeleteCustomerCommand(customer_id="cust-1"))

    assert uow.committed is False


async def test_delete_succeeds_when_only_cancelled_orders_exist() -> None:
    """Customer with only CANCELLED orders can be deleted."""
    customer = _make_customer()
    order = _make_order(customer_id="cust-1", status=OrderStatus.CANCELLED)
    customer_repo = FakeCustomerRepository({"cust-1": customer})
    order_repo = FakeOrderRepository(orders=[order])
    uow = FakeUnitOfWork(customers=customer_repo, orders=order_repo)
    use_case = DeleteCustomerUseCase(uow)

    await use_case.execute(DeleteCustomerCommand(customer_id="cust-1"))

    assert uow.committed is True
    assert await customer_repo.get_by_id("cust-1") is None


async def test_delete_succeeds_when_only_fulfilled_orders_exist() -> None:
    """Customer with only FULFILLED orders can be deleted."""
    customer = _make_customer()
    order = _make_order(customer_id="cust-1", status=OrderStatus.FULFILLED)
    customer_repo = FakeCustomerRepository({"cust-1": customer})
    order_repo = FakeOrderRepository(orders=[order])
    uow = FakeUnitOfWork(customers=customer_repo, orders=order_repo)
    use_case = DeleteCustomerUseCase(uow)

    await use_case.execute(DeleteCustomerCommand(customer_id="cust-1"))

    assert uow.committed is True
