"""ListProducts use case — returns a paginated, optionally price-filtered product page."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.application.unit_of_work import UnitOfWork
from app.domain.errors import InvalidPaginationError, InvalidPriceRangeError
from app.domain.products.entities import Price, ProductPage

_DEFAULT_SIZE = 20
_MAX_SIZE = 100


@dataclass(frozen=True)
class ListProductsQuery:
    """Input query for the ListProducts use case."""

    page: int = 1
    size: int = _DEFAULT_SIZE
    min_price: Decimal | None = field(default=None)
    max_price: Decimal | None = field(default=None)


class ListProductsUseCase:
    """Return a page of products optionally filtered by price range."""

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: ListProductsQuery) -> ProductPage:
        """Validate query parameters, then delegate to the repository."""
        self._validate(query)

        min_price = Price(query.min_price) if query.min_price is not None else None
        max_price = Price(query.max_price) if query.max_price is not None else None

        async with self._uow:
            return await self._uow.products.list(
                page=query.page,
                size=query.size,
                min_price=min_price,
                max_price=max_price,
            )

    @staticmethod
    def _validate(query: ListProductsQuery) -> None:
        if query.page < 1:
            raise InvalidPaginationError("page must be >= 1.")
        if query.size < 1:
            raise InvalidPaginationError("size must be >= 1.")
        if query.size > _MAX_SIZE:
            raise InvalidPaginationError(f"size must be <= {_MAX_SIZE}.")
        if query.min_price is not None and query.min_price < Decimal("0"):
            raise InvalidPriceRangeError("min_price must be non-negative.")
        if query.max_price is not None and query.max_price < Decimal("0"):
            raise InvalidPriceRangeError("max_price must be non-negative.")
        if (
            query.min_price is not None
            and query.max_price is not None
            and query.max_price < query.min_price
        ):
            raise InvalidPriceRangeError("max_price must be >= min_price.")
