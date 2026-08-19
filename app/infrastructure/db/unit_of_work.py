"""SQLAlchemy implementation of the UnitOfWork application port."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.customers.entities import EmailConflictError
from app.domain.customers.ports import CustomerRepository
from app.domain.errors import SkuConflictError
from app.domain.inventory.ports import InventoryRepository
from app.domain.orders.ports import OrderRepository
from app.domain.products.ports import ProductRepository
from app.infrastructure.db.repositories.customers import SqlAlchemyCustomerRepository
from app.infrastructure.db.repositories.inventory import SqlAlchemyInventoryRepository
from app.infrastructure.db.repositories.orders import SqlAlchemyOrderRepository
from app.infrastructure.db.repositories.products import SqlAlchemyProductRepository


class SqlAlchemyUnitOfWork:
    """Manages a single SQLAlchemy async session as a unit of work."""

    products: ProductRepository
    customers: CustomerRepository
    inventory: InventoryRepository
    orders: OrderRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self.products = SqlAlchemyProductRepository(self._session)
        self.customers = SqlAlchemyCustomerRepository(self._session)
        self.inventory = SqlAlchemyInventoryRepository(self._session)
        self.orders = SqlAlchemyOrderRepository(self._session)
        return self

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._session is None:
            return
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        """Flush and commit the current session."""
        if self._session is None:
            return
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            orig = str(exc.orig)
            # Translate DB-level unique constraint violation on SKU to domain error.
            if "uq_products_sku" in orig:
                raise SkuConflictError(orig) from exc
            # Translate DB-level unique constraint violation on customer email to domain error.
            if "uq_customers_email" in orig:
                raise EmailConflictError(orig) from exc
            raise

    async def rollback(self) -> None:
        """Rollback the current session."""
        if self._session is not None:
            await self._session.rollback()
