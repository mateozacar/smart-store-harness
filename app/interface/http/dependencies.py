"""FastAPI dependency injection wiring."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.create_product import CreateProductUseCase
from app.application.list_products import ListProductsUseCase
from app.application.register_customer import RegisterCustomerUseCase
from app.infrastructure.db.session import session_factory as _default_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

# Module-level override; set by create_app() when a test session factory is provided.
_override_session_factory: async_sessionmaker[AsyncSession] | None = None


def set_session_factory(factory: async_sessionmaker[AsyncSession]) -> None:
    """Configure the module-level session factory (called by create_app for tests)."""
    global _override_session_factory  # noqa: PLW0603
    _override_session_factory = factory


def _get_uow() -> SqlAlchemyUnitOfWork:
    """Provide a SqlAlchemyUnitOfWork for the current request."""
    factory = (
        _override_session_factory
        if _override_session_factory is not None
        else _default_session_factory
    )
    return SqlAlchemyUnitOfWork(factory)


def _get_create_product_use_case(
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(_get_uow)],
) -> CreateProductUseCase:
    """Provide a CreateProductUseCase for the current request."""
    return CreateProductUseCase(uow)


def _get_list_products_use_case(
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(_get_uow)],
) -> ListProductsUseCase:
    """Provide a ListProductsUseCase for the current request."""
    return ListProductsUseCase(uow)


def _get_register_customer_use_case(
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(_get_uow)],
) -> RegisterCustomerUseCase:
    """Provide a RegisterCustomerUseCase for the current request."""
    return RegisterCustomerUseCase(uow)


get_create_product_use_case: Annotated[
    CreateProductUseCase, Depends(_get_create_product_use_case)
] = Depends(_get_create_product_use_case)

get_list_products_use_case: Annotated[ListProductsUseCase, Depends(_get_list_products_use_case)] = (
    Depends(_get_list_products_use_case)
)

get_register_customer_use_case: Annotated[
    RegisterCustomerUseCase, Depends(_get_register_customer_use_case)
] = Depends(_get_register_customer_use_case)
