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
