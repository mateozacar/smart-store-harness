# Task: Product Detail Endpoint

Implement `GET /api/v1/products/{sku}` that returns a single product including its derived `available` field.

You are working on the branch `feat/products-get-by-sku` in its own git worktree.
Follow the hexagonal architecture described in `docs/ARCHITECTURE.md`.
Follow the quality rules in `docs/BEST_PRACTICES.md` and `.claude/rules/python.md`.

---

## What to build

### GET /api/v1/products/{sku}

Returns a single product. Includes the derived `available` quantity from inventory.

Response 200:
```json
{
  "id": "uuid",
  "sku": "SKU-A",
  "name": "Widget",
  "price": "9.99",
  "available": 7
}
```

`available` is `on_hand - reserved` from the inventory row for this SKU.
If no inventory row exists for the SKU, `available` is `null` (not an error).

Response 404 (problem+json, type `product-not-found`) if the SKU does not exist in products.

---

## Files to create or modify

### Phase 1 — Production code

**1. Application: create `app/application/get_product.py`**

`GetProductQuery(sku: str)` + `GetProductUseCase` that:
- Calls `uow.products.get_by_sku(SKU(sku))` — raises `ProductNotFoundError` if None
- Calls `uow.inventory.get(SKU(sku))` (non-locking) to fetch inventory — catches `DomainError("inventory-not-found", ...)` and treats it as `available=None`
- Returns a result object (dataclass) with `product: Product` and `available: int | None`

Both calls happen inside the same `async with self._uow` block (read-only, no commit needed).

**2. Add `ProductNotFoundError` to `app/domain/errors.py` if it does not exist.**

```python
class ProductNotFoundError(DomainError):
    problem_type = "product-not-found"
    http_status = 404
    def __init__(self, sku: str) -> None:
        super().__init__("product-not-found", f"Product with SKU '{sku}' not found.")
        self.sku = sku
```

**3. Interface schemas: add `ProductDetailResponse` to `app/interface/schemas/products.py`**

```python
class ProductDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    sku: str
    name: str
    price: str
    available: int | None
```

**4. Interface router: add the `GET /{sku}` endpoint to `app/interface/http/routers/products.py`**

Add below the existing `POST ""` handler:
```python
@router.get("/{sku}", status_code=200, response_model=ProductDetailResponse, ...)
async def get_product(sku: str, use_case: GetProductUseCase = get_get_product_use_case) -> ProductDetailResponse:
    ...
```

Document the 404 response in the `responses=` dict using problem+json format.

**5. DI wiring: add `_get_get_product_use_case` to `app/interface/http/dependencies.py`**

Follow the existing pattern for `_get_create_product_use_case`.

Note: `GetProductUseCase` needs access to both `uow.products` and `uow.inventory`.
The existing `UnitOfWork` already exposes both — no changes needed there.

After all production code: run `uv run ruff check app && uv run ruff format --check app && uv run mypy app`. Fix all errors. Commit as `feat: GET /products/{sku} with derived available field`.

---

### Phase 2 — Tests

Write tests in:
- `tests/unit/application/test_get_product.py` — found with inventory, found without inventory row (available=None), SKU not found (404)
- `tests/e2e/test_products_detail.py` — GET 200 with inventory seeded, GET 200 with no inventory (available=null), GET 404

After writing all tests: run `uv run pytest -x -q`, then `uv run pytest tests/ --cov=app --cov-report=term-missing`.
Commit as `test: GET /products/{sku} scenarios and edge cases`.
