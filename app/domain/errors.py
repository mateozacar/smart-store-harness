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
    """Raised when a customer_id reference is invalid (e.g. during order placement).

    http_status 422: the caller supplied an id that does not resolve to a customer,
    making the request semantically invalid (validation failure).
    """

    problem_type = "customer-not-found"
    http_status = 422

    def __init__(self, customer_id: str) -> None:
        super().__init__(
            "customer-not-found",
            f"Customer with id '{customer_id}' does not exist.",
        )
        self.customer_id = customer_id


class CustomerDeleteNotFoundError(DomainError):
    """Raised by DeleteCustomerUseCase when the target customer does not exist.

    http_status 404: the addressed resource was not found.
    Uses the same problem_type as CustomerNotFoundError so clients need only
    handle one type URI for 'customer not found' regardless of the HTTP status.
    """

    problem_type = "customer-not-found"
    http_status = 404

    def __init__(self, customer_id: str) -> None:
        super().__init__(
            "customer-not-found",
            f"Customer with id '{customer_id}' does not exist.",
        )
        self.customer_id = customer_id


class CustomerHasActiveOrdersError(DomainError):
    """Raised when attempting to delete a customer who has PENDING or CONFIRMED orders."""

    problem_type = "customer-has-active-orders"
    http_status = 409

    def __init__(self, customer_id: str) -> None:
        super().__init__(
            "customer-has-active-orders",
            f"Customer '{customer_id}' has active orders and cannot be deleted.",
        )
        self.customer_id = customer_id
