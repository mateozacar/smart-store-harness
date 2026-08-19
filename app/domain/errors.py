"""Domain error hierarchy for Smart Store."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain errors."""

    problem_type: str = "domain-error"
    http_status: int = 422

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class SkuConflictError(DomainError):
    """Raised when a product with the same SKU already exists."""

    problem_type = "sku-conflict"
    http_status = 409

    def __init__(self, sku: str) -> None:
        super().__init__("sku-conflict", f"A product with SKU '{sku}' already exists.")
        self.sku = sku


class InvalidPaginationError(DomainError):
    """Raised when pagination parameters are out of the allowed range."""

    problem_type = "invalid-pagination"
    http_status = 422

    def __init__(self, detail: str) -> None:
        super().__init__("invalid-pagination", detail)


class InvalidPriceRangeError(DomainError):
    """Raised when price range bounds are invalid (negative or max < min)."""

    problem_type = "invalid-price-range"
    http_status = 422

    def __init__(self, detail: str) -> None:
        super().__init__("invalid-price-range", detail)


class CustomerNotFoundError(DomainError):
    """Raised when a referenced customer_id does not exist."""

    problem_type = "customer-not-found"
    http_status = 422

    def __init__(self, customer_id: str) -> None:
        super().__init__(
            "customer-not-found",
            f"Customer with id '{customer_id}' does not exist.",
        )
        self.customer_id = customer_id
