"""FastAPI router for /api/v1/products."""

from __future__ import annotations

from fastapi import APIRouter, Response

from app.application.create_product import CreateProductCommand, CreateProductUseCase
from app.interface.http.dependencies import get_create_product_use_case
from app.interface.schemas.products import CreateProductRequest, ProductResponse

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post(
    "",
    status_code=201,
    response_model=ProductResponse,
    responses={
        409: {
            "description": "A product with the same SKU already exists.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/sku-conflict",
                        "title": "Sku Conflict",
                        "status": 409,
                        "detail": "A product with SKU 'WIDGET-01' already exists.",
                        "sku": "WIDGET-01",
                    }
                }
            },
        }
    },
)
async def create_product(
    body: CreateProductRequest,
    response: Response,
    use_case: CreateProductUseCase = get_create_product_use_case,
) -> ProductResponse:
    """Create a new product in the catalog.

    Returns 201 with the created product and a Location header.
    Returns 409 if a product with the same SKU already exists.
    Returns 422 if the request body is invalid (e.g. negative price).
    """
    product = await use_case.execute(
        CreateProductCommand(sku=body.sku, name=body.name, price=body.price)
    )
    response.headers["Location"] = f"/api/v1/products/{product.sku.value}"
    return ProductResponse(
        id=product.id,
        sku=product.sku.value,
        name=product.name,
        price=str(product.price.value),
    )
