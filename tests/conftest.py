"""Shared pytest fixtures for all test layers."""

import os
import time

import psycopg
import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from alembic import command

# Disable the Ryuk reaper container — it causes issues in some local environments.
os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

_HOST_PORT_READY_RETRIES = 10
_HOST_PORT_READY_INTERVAL = 1.0


def _to_psycopg_url(raw_url: str) -> str:
    """Convert a testcontainers psycopg2 URL to psycopg (v3) driver URL."""
    url = raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://")
    if not url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql://", "postgresql+psycopg://")
    return url


def _wait_for_host_port(host: str, port: int, user: str, password: str, dbname: str) -> None:
    """Wait until the Postgres port is reachable from the host.

    testcontainers validates liveness by exec-ing psql inside the container,
    which is faster than the host-side port mapping becoming available.
    """
    last_error: Exception = RuntimeError("never connected")
    for _ in range(_HOST_PORT_READY_RETRIES):
        try:
            conn = psycopg.connect(
                host=host,
                port=port,
                dbname=dbname,
                user=user,
                password=password,
                connect_timeout=5,
            )
            conn.execute("SELECT 1")
            conn.close()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(_HOST_PORT_READY_INTERVAL)
    raise RuntimeError(
        f"Postgres host port {host}:{port} not ready after "
        f"{_HOST_PORT_READY_RETRIES} retries: {last_error}"
    )


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:  # type: ignore[misc]
    """Start a Postgres 16 testcontainer for the test session."""
    with PostgresContainer("postgres:16-alpine") as pg:
        # The testcontainers wait strategy validates via psql inside the container.
        # Wait for the host-side port mapping to become reachable too.
        _wait_for_host_port(
            host=pg.get_container_host_ip(),
            port=int(pg.get_exposed_port(5432)),
            user=pg.username,
            password=pg.password,
            dbname=pg.dbname,
        )
        yield pg


@pytest.fixture(scope="session")
async def pg_engine(postgres_container: PostgresContainer):  # type: ignore[no-untyped-def]
    """Create an async SQLAlchemy engine and run Alembic migrations.

    Depends directly on postgres_container so the container stays alive
    for the full lifetime of the engine fixture.
    """
    raw_url = postgres_container.get_connection_url()
    psycopg_url = _to_psycopg_url(raw_url)

    # Run migrations via the synchronous psycopg driver (alembic env.py uses sync engine)
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", psycopg_url)
    command.upgrade(cfg, "head")

    engine = create_async_engine(psycopg_url, echo=False)
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
