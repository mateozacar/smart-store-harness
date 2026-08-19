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
