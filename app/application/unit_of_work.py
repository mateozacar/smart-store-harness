"""UnitOfWork protocol — the transaction boundary for application use cases."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class UnitOfWork(Protocol):
    """Defines the commit/rollback boundary used by application use cases."""

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, *args: object) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
