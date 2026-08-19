"""Pydantic schemas for the /products endpoint."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class CreateProductRequest(BaseModel):
    """Request body for POST /api/v1/products."""

    model_config = ConfigDict(extra="forbid")

    sku: str
    name: str
    price: Decimal

    @field_validator("price")
    @classmethod
    def price_must_be_non_negative(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("price must be non-negative")
        return v


class ProductResponse(BaseModel):
    """Response body for product endpoints."""

    model_config = ConfigDict(extra="forbid")

    id: str
    sku: str
    name: str
    price: str
