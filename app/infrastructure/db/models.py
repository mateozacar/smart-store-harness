"""SQLAlchemy ORM models — separate from domain entities."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Shared declarative base."""


class ProductRow(Base):
    """ORM model for the products table."""

    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("sku", name="uq_products_sku"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sku: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[str] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    order_lines: Mapped[list["OrderLineRow"]] = relationship(back_populates="product")


class InventoryRow(Base):
    """ORM model for the inventory table."""

    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("on_hand >= 0", name="ck_inventory_on_hand_nonneg"),
        CheckConstraint("reserved >= 0", name="ck_inventory_reserved_nonneg"),
        CheckConstraint("on_hand >= reserved", name="ck_inventory_on_hand_ge_reserved"),
    )

    sku: Mapped[str] = mapped_column(String(32), primary_key=True)
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)


class CustomerRow(Base):
    """ORM model for the customers table."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("email", name="uq_customers_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    orders: Mapped[list["OrderRow"]] = relationship(back_populates="customer")


class OrderRow(Base):
    """ORM model for the orders table."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    customer: Mapped["CustomerRow | None"] = relationship(back_populates="orders")
    lines: Mapped[list["OrderLineRow"]] = relationship(back_populates="order")


class OrderLineRow(Base):
    """ORM model for order lines (child of orders)."""

    __tablename__ = "order_lines"
    __table_args__ = (CheckConstraint("quantity > 0", name="ck_order_lines_quantity_positive"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id: Mapped[str] = mapped_column(String(36), ForeignKey("orders.id"), nullable=False)
    sku: Mapped[str] = mapped_column(String(32), ForeignKey("products.sku"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["OrderRow"] = relationship(back_populates="lines")
    product: Mapped["ProductRow"] = relationship(back_populates="order_lines")
