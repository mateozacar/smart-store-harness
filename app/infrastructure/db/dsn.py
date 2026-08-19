"""DATABASE_URL normalization.

Render's managed Postgres exposes the DSN as `postgresql://…` (no driver
hint). SQLAlchemy resolves that scheme to psycopg2, which is not part of
our pinned toolchain. Normalize everywhere to psycopg v3, which supports
both sync (Alembic) and async (runtime app) engines against the same DSN.
"""


def normalize_database_url(dsn: str) -> str:
    """Return `dsn` rewritten to use the psycopg v3 driver."""
    for old in ("postgresql://", "postgres://", "postgresql+psycopg2://"):
        if dsn.startswith(old):
            return dsn.replace(old, "postgresql+psycopg://", 1)
    if dsn.startswith("postgresql+asyncpg://"):
        return dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return dsn
