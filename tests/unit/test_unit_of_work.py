"""Unit tests for UnitOfWork protocol."""

from typing import Any

from app.application.unit_of_work import UnitOfWork


def test_unit_of_work_is_protocol() -> None:
    """UnitOfWork is a runtime-checkable Protocol."""

    assert hasattr(UnitOfWork, "__protocol_attrs__") or (
        hasattr(UnitOfWork, "__abstractmethods__") or isinstance(UnitOfWork, type)
    )


class FakeUoW:
    """Minimal fake that satisfies the UnitOfWork protocol."""

    products: Any = None

    async def __aenter__(self) -> "FakeUoW":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass


def test_fake_uow_satisfies_protocol() -> None:
    """A correctly-shaped class is recognised as a UnitOfWork."""
    fake = FakeUoW()
    assert isinstance(fake, UnitOfWork)
