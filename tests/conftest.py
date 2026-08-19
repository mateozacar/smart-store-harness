"""Shared pytest fixtures for all test layers."""

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from alembic import command


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    """Start a Postgres 16 testcontainer for the test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
async def pg_engine(postgres_container: PostgresContainer):  # type: ignore[no-untyped-def]
    """Create an async engine pointing at the test container and run migrations."""
    sync_url = postgres_container.get_connection_url()
    # testcontainers returns a psycopg2 URL; convert to async psycopg
    async_url = sync_url.replace("postgresql+psycopg2", "postgresql+psycopg").replace(
        "postgresql://", "postgresql+psycopg://"
    )
    if not async_url.startswith("postgresql+psycopg://"):
        async_url = async_url.replace("postgresql://", "postgresql+psycopg://")

    engine = create_async_engine(async_url, echo=False)

    # Run migrations using a sync DSN (alembic env.py uses synchronous engine)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(cfg, "head")

    yield engine
    await engine.dispose()


@pytest.fixture(scope="session")
def pg_session_factory(  # type: ignore[no-untyped-def]
    pg_engine,
) -> async_sessionmaker[AsyncSession]:
    """Return a session factory bound to the test container engine."""
    return async_sessionmaker(
        pg_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
