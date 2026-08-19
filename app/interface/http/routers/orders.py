"""FastAPI router for /api/v1/orders."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.application.place_order import PlaceOrderCommand, PlaceOrderUseCase
from app.interface.http.dependencies import get_place_order_use_case
from app.interface.schemas.orders import (
    CreateOrderRequest,
    OrderLineResponse,
    OrderResponse,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


@router.post(
    "",
    status_code=201,
    response_model=OrderResponse,
    responses={
        409: {
            "description": "Insufficient stock to fulfill one or more order lines.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/insufficient-stock",
                        "title": "Insufficient Stock",
                        "status": 409,
                        "detail": "Requested 5 units of SKU-A but only 2 available.",
                        "sku": "SKU-A",
                        "requested": 5,
                        "available": 2,
                    }
                }
            },
        },
        422: {
            "description": "Invalid order payload or customer not found.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/customer-not-found",
                        "title": "Customer Not Found",
                        "status": 422,
                        "detail": "Customer with id 'unknown-id' does not exist.",
                    }
                }
            },
        },
    },
)
async def create_order(
    body: CreateOrderRequest,
    response: Response,
    use_case: PlaceOrderUseCase = get_place_order_use_case,
) -> OrderResponse:
    """Create an order with atomic inventory reservation.

    Optionally attaches the order to a registered customer.
    Returns 201 with the created order and a Location header.
    Returns 409 if any line has insufficient stock.
    Returns 422 if the customer_id references a non-existent customer.
    """
    cmd = PlaceOrderCommand(
        customer_id=body.customer_id,
        lines=tuple((line.sku, line.quantity) for line in body.lines),
    )
    order = await use_case.execute(cmd)
    response.headers["Location"] = f"/api/v1/orders/{order.id}"
    return OrderResponse(
        id=order.id,
        status=order.status.value,
        customer_id=order.customer_id,
        lines=[
            OrderLineResponse(sku=line.sku.value, quantity=line.quantity) for line in order.lines
        ],
    )
