"""Add password_hash column to customers table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Add password_hash VARCHAR(255) to customers.

    The column is NOT NULL with a server_default of '' so the migration succeeds
    on tables that already have rows (e.g. staging deployments that registered
    customers before auth was introduced). Those rows will have an empty hash and
    cannot authenticate; they must re-register.
    """
    op.add_column(
        "customers",
        sa.Column(
            "password_hash",
            sa.String(255),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    """Remove the password_hash column from customers."""
    op.drop_column("customers", "password_hash")
