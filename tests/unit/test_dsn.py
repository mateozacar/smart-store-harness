"""Unit tests for DATABASE_URL normalization.

Regression coverage for the deploy incident where Render's raw DSN
(`postgresql://…` with no driver hint) caused SQLAlchemy to resolve
psycopg2, which is not installed. Both the Alembic env and the runtime
config must normalize to `postgresql+psycopg://` (psycopg v3).
"""

from app.infrastructure.db.dsn import normalize_database_url


def test_render_style_postgres_scheme_normalized_to_psycopg_v3() -> None:
    assert (
        normalize_database_url("postgres://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_postgresql_scheme_without_driver_normalized_to_psycopg_v3() -> None:
    assert (
        normalize_database_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_psycopg2_driver_replaced_with_psycopg_v3() -> None:
    assert (
        normalize_database_url("postgresql+psycopg2://u:p@h:5432/db")
        == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_asyncpg_driver_swapped_for_psycopg_v3() -> None:
    assert (
        normalize_database_url("postgresql+asyncpg://u:p@h:5432/db")
        == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_already_normalized_dsn_untouched() -> None:
    assert (
        normalize_database_url("postgresql+psycopg://u:p@h:5432/db")
        == "postgresql+psycopg://u:p@h:5432/db"
    )


def test_query_string_preserved() -> None:
    assert (
        normalize_database_url("postgres://u:p@h:5432/db?sslmode=require")
        == "postgresql+psycopg://u:p@h:5432/db?sslmode=require"
    )
