"""FastAPI router for /api/v1/products."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.application.create_product import CreateProductCommand, CreateProductUseCase
from app.application.get_product_detail import GetProductDetailQuery, GetProductDetailUseCase
from app.application.list_products import ListProductsQuery, ListProductsUseCase
from app.interface.http.dependencies import (
    get_create_product_use_case,
    get_get_product_detail_use_case,
    get_list_products_use_case,
)
from app.interface.schemas.products import (
    CreateProductRequest,
    ProductDetailResponse,
    ProductPageResponse,
    ProductResponse,
)

router = APIRouter(prefix="/api/v1/products", tags=["products"])

# Module-level Query metadata singletons (required by ruff B008 — no function calls in defaults).
# When used in Annotated[], the default value is placed on the parameter itself (with =).
_PageQuery = Query(ge=1, description="1-based page number.")
_SizeQuery = Query(ge=1, le=100, description="Page size (max 100).")
# Price bounds: non-negativity is enforced by the domain layer (InvalidPriceRangeError → 422).
_MinPriceQuery = Query(description="Inclusive lower price bound.")
_MaxPriceQuery = Query(description="Inclusive upper price bound.")


@router.get(
    "",
    status_code=200,
    response_model=ProductPageResponse,
    responses={
        422: {
            "description": "Invalid pagination parameters or price range.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/invalid-price-range",
                        "title": "Invalid Price Range",
                        "status": 422,
                        "detail": "max_price must be >= min_price.",
                    }
                }
            },
        }
    },
)
async def list_products(
    page: Annotated[int, _PageQuery] = 1,
    size: Annotated[int, _SizeQuery] = 20,
    min_price: Annotated[Decimal | None, _MinPriceQuery] = None,
    max_price: Annotated[Decimal | None, _MaxPriceQuery] = None,
    use_case: ListProductsUseCase = get_list_products_use_case,
) -> ProductPageResponse:
    """List products with optional price range filter, ordered by creation date descending.

    Returns 200 with a paginated JSON object: { items, total, page, size }.
    Returns 422 problem+json when price bounds are invalid (negative or max < min).
    """
    product_page = await use_case.execute(
        ListProductsQuery(page=page, size=size, min_price=min_price, max_price=max_price)
    )
    return ProductPageResponse(
        items=[
            ProductResponse(
                id=p.id,
                sku=p.sku.value,
                name=p.name,
                price=str(p.price.value),
            )
            for p in product_page.items
        ],
        total=product_page.total,
        page=product_page.page,
        size=product_page.size,
    )


@router.get(
    "/{sku}",
    status_code=200,
    response_model=ProductDetailResponse,
    responses={
        404: {
            "description": "No product with the given SKU exists.",
            "content": {
                "application/problem+json": {
                    "example": {
                        "type": "https://smart-store.example/problems/product-not-found",
                        "title": "Product Not Found",
                        "status": 404,
                        "detail": "No product with SKU 'GHOST-01' exists.",
                        "sku": "GHOST-01",
                    }
                }
            },
        }
    },
)
async def get_product_detail(
    sku: str,
    use_case: GetProductDetailUseCase = get_get_product_detail_use_case,
) -> ProductDetailResponse:
    """Retrieve a product with its current available stock.

    Returns 200 with the product and computed available quantity.
    Returns 404 problem+json if no product with the given SKU exists.
    """
    detail = await use_case.execute(GetProductDetailQuery(sku=sku))
    return ProductDetailResponse(
        id=detail.id,
        sku=detail.sku,
        name=detail.name,
        price=str(detail.price),
        available=detail.available,
    )


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
