"""Create initial tables: products, inventory, orders, customers.

Revision ID: 0001
Revises:
Create Date: 2026-08-19

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the four core tables with PRD §3 invariants."""
    op.create_table(
        "products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sku", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
        sa.CheckConstraint("price >= 0", name="ck_products_price_nonneg"),
    )

    op.create_table(
        "inventory",
        sa.Column("sku", sa.String(32), primary_key=True),
        sa.Column("on_hand", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("on_hand >= 0", name="ck_inventory_on_hand_nonneg"),
        sa.CheckConstraint("reserved >= 0", name="ck_inventory_reserved_nonneg"),
        sa.CheckConstraint("on_hand >= reserved", name="ck_inventory_on_hand_ge_reserved"),
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("email", name="uq_customers_email"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id"),
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.String(32),
            sa.ForeignKey("products.sku"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_lines_quantity_positive"),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("customers")
    op.drop_table("inventory")
    op.drop_table("products")
