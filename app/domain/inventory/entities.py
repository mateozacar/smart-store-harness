"""Inventory domain entities and value objects."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.errors import DomainError
from app.domain.products.entities import SKU


class InsufficientStockError(DomainError):
    """Raised when requested quantity exceeds available inventory."""

    problem_type = "insufficient-stock"
    http_status = 409

    def __init__(self, sku: SKU, requested: int, available: int) -> None:
        super().__init__(
            "insufficient-stock",
            f"Requested {requested} units of {sku.value} but only {available} available.",
        )
        self.sku = sku.value
        self.requested = requested
        self.available = available


@dataclass
class InventoryLevel:
    """Aggregate root for inventory levels per SKU.

    Invariants:
    - on_hand >= 0
    - reserved >= 0
    - on_hand >= reserved at all times
    - available = on_hand - reserved (never stored, always computed)
    """

    sku: SKU
    on_hand: int
    reserved: int = 0

    def available(self) -> int:
        """Compute the available quantity (on_hand - reserved)."""
        return self.on_hand - self.reserved

    def reserve(self, qty: int) -> None:
        """Reserve qty units, raising InsufficientStockError if unavailable.

        Raises:
            DomainError: if qty <= 0.
            InsufficientStockError: if qty > available.
        """
        if qty <= 0:
            raise DomainError("invalid-quantity", "Quantity must be positive.")
        if qty > self.available():
            raise InsufficientStockError(self.sku, requested=qty, available=self.available())
        self.reserved += qty

    def release(self, qty: int) -> None:
        """Release qty units of reservation back to available.

        Raises:
            DomainError: if qty <= 0 or qty > reserved.
        """
        if qty <= 0 or qty > self.reserved:
            raise DomainError("invalid-release", "Cannot release more than reserved.")
        self.reserved -= qty

    def commit(self, qty: int) -> None:
        """Commit qty units: decrement on_hand and reserved together.

        Raises:
            DomainError: if qty <= 0 or qty > reserved.
        """
        if qty <= 0 or qty > self.reserved:
            raise DomainError("invalid-commit", "Cannot commit more than reserved.")
        self.reserved -= qty
        self.on_hand -= qty
