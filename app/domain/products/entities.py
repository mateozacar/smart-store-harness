"""Product domain entities and value objects."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.errors import DomainError

_SKU_MAX_LEN = 32


@dataclass(frozen=True, slots=True)
class SKU:
    """Value object representing a product SKU."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > _SKU_MAX_LEN:
            raise DomainError("sku-invalid", "SKU must be 1..32 characters.")
        if not self.value.replace("-", "").isalnum():
            raise DomainError("sku-invalid", "SKU must be alphanumeric with dashes only.")


@dataclass(frozen=True, slots=True)
class Price:
    """Value object representing a non-negative product price with two decimal places."""

    value: Decimal

    def __post_init__(self) -> None:
        if self.value < Decimal("0"):
            raise DomainError("price-invalid", "Price must be non-negative.")


@dataclass
class Product:
    """Product aggregate root."""

    sku: SKU
    name: str
    price: Price
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass(frozen=True)
class ProductPage:
    """Value object representing a paginated page of products."""

    items: tuple[Product, ...]
    total: int
    page: int
    size: int

    def __init__(
        self,
        items: list[Product] | tuple[Product, ...],
        total: int,
        page: int,
        size: int,
    ) -> None:
        object.__setattr__(self, "items", tuple(items))
        object.__setattr__(self, "total", total)
        object.__setattr__(self, "page", page)
        object.__setattr__(self, "size", size)
