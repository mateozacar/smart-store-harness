"""UnitOfWork protocol — the transaction boundary for application use cases."""

from typing import Protocol, runtime_checkable

from app.domain.products.ports import ProductRepository


@runtime_checkable
class UnitOfWork(Protocol):
    """Defines the commit/rollback boundary used by application use cases."""

    products: ProductRepository

    async def __aenter__(self) -> "UnitOfWork": ...  # pragma: no cover

    async def __aexit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> None: ...  # pragma: no cover

    async def commit(self) -> None: ...  # pragma: no cover

    async def rollback(self) -> None: ...  # pragma: no cover
