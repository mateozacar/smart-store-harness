"""Pydantic request/response models for the orders endpoint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OrderLineRequest(BaseModel):
    """A single line item in a create-order request."""

    model_config = ConfigDict(extra="forbid")

    sku: str = Field(..., min_length=1, max_length=32, description="Product SKU.")
    quantity: int = Field(..., gt=0, description="Number of units to order.")


class CreateOrderRequest(BaseModel):
    """Request body for POST /api/v1/orders."""

    model_config = ConfigDict(extra="forbid")

    customer_id: str | None = Field(
        default=None,
        description="Optional customer ID to attach to this order.",
    )
    lines: list[OrderLineRequest] = Field(
        ...,
        min_length=1,
        description="Non-empty list of order lines.",
    )


class OrderLineResponse(BaseModel):
    """A single line item in an order response."""

    model_config = ConfigDict(extra="forbid")

    sku: str
    quantity: int


class OrderResponse(BaseModel):
    """Response body for a created or retrieved order."""

    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    customer_id: str | None
    lines: list[OrderLineResponse]
