"""Fake implementations of domain ports for unit testing."""

from __future__ import annotations

from app.domain.customers.entities import Customer, Email, EmailConflictError
from app.domain.errors import DomainError
from app.domain.inventory.entities import InventoryLevel
from app.domain.orders.entities import Order
from app.domain.products.entities import SKU


class FakeInventoryRepository:
    """In-memory inventory repository for unit testing."""

    def __init__(self, stock: dict[str, tuple[int, int]] | None = None) -> None:
        # stock maps sku_value -> (on_hand, reserved)
        self.state: dict[str, InventoryLevel] = {}
        if stock:
            for sku_value, (on_hand, reserved) in stock.items():
                self.state[sku_value] = InventoryLevel(
                    sku=SKU(sku_value), on_hand=on_hand, reserved=reserved
                )

    async def get(self, sku: SKU) -> InventoryLevel | None:
        return self.state.get(sku.value)

    async def get_for_update(self, sku: SKU) -> InventoryLevel:
        if sku.value not in self.state:
            raise DomainError("inventory-not-found", f"No inventory record for SKU '{sku.value}'.")
        return self.state[sku.value]

    async def save(self, level: InventoryLevel) -> None:
        self.state[level.sku.value] = level


class FakeOrderRepository:
    """In-memory order repository for unit testing."""

    def __init__(self) -> None:
        self.saved: list[Order] = []

    async def add(self, order: Order) -> None:
        self.saved.append(order)


class FakeCustomerRepository:
    """In-memory customer repository for unit testing."""

    def __init__(self, customers: dict[str, Customer] | None = None) -> None:
        # keyed by customer id
        self._by_id: dict[str, Customer] = {}
        self._by_email: dict[str, Customer] = {}
        if customers:
            for cid, customer in customers.items():
                self._by_id[cid] = customer
                self._by_email[customer.email.value] = customer

    async def add(self, customer: Customer) -> None:
        if customer.email.value in self._by_email:
            raise EmailConflictError(customer.email.value)
        self._by_id[customer.id] = customer
        self._by_email[customer.email.value] = customer

    async def get_by_email(self, email: Email) -> Customer | None:
        return self._by_email.get(email.value)

    async def get_by_id(self, customer_id: str) -> Customer | None:
        return self._by_id.get(customer_id)


class FakeUnitOfWork:
    """In-memory unit of work for unit testing the PlaceOrder use case."""

    def __init__(
        self,
        inventory: FakeInventoryRepository | None = None,
        orders: FakeOrderRepository | None = None,
        customers: FakeCustomerRepository | None = None,
    ) -> None:
        self.inventory: FakeInventoryRepository = inventory or FakeInventoryRepository()
        self.orders: FakeOrderRepository = orders or FakeOrderRepository()
        self.customers: FakeCustomerRepository = customers or FakeCustomerRepository()
        # products required by UnitOfWork Protocol; not used by PlaceOrderUseCase
        self.products: object = None
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        pass

    @classmethod
    def with_stock(
        cls,
        stock: dict[str, tuple[int, int]],
        customers: dict[str, Customer] | None = None,
    ) -> FakeUnitOfWork:
        """Factory for creating a UoW with pre-seeded inventory."""
        inv = FakeInventoryRepository(stock)
        cust = FakeCustomerRepository(customers)
        return cls(inventory=inv, customers=cust)
