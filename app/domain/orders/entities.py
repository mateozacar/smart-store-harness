"""Order domain entities and value objects."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.domain.errors import DomainError
from app.domain.products.entities import SKU


class OrderStatus(Enum):
    """Possible states for an order."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class OrderLine:
    """Immutable value object representing a single order line."""

    sku: SKU
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise DomainError("invalid-quantity", "Order line quantity must be greater than zero.")


@dataclass
class Order:
    """Order aggregate root.

    Invariants:
    - lines is non-empty after creation
    - All line quantities are strictly positive
    - customer_id may be None (anonymous order)
    - Status begins at PENDING
    """

    id: str
    status: OrderStatus
    lines: list[OrderLine] = field(default_factory=list)
    customer_id: str | None = None

    @classmethod
    def new(cls, customer_id: str | None = None) -> Order:
        """Create a new order in PENDING state."""
        return cls(
            id=str(uuid.uuid4()),
            status=OrderStatus.PENDING,
            lines=[],
            customer_id=customer_id,
        )

    def add_line(self, line: OrderLine) -> None:
        """Append an order line to this order."""
        self.lines.append(line)
