# Task: Inventory Router

Implement `GET /api/v1/inventory/{sku}` and `PATCH /api/v1/inventory/{sku}` in the Smart Store API.

You are working on the branch `feat/inventory-router` in its own git worktree.
Follow the hexagonal architecture described in `docs/ARCHITECTURE.md`.
Follow the quality rules in `docs/BEST_PRACTICES.md` and `.claude/rules/python.md`.

---

## What to build

### GET /api/v1/inventory/{sku}
Returns the current inventory level for a SKU.

Response 200:
```json
{ "sku": "SKU-A", "on_hand": 10, "reserved": 3, "available": 7 }
```
Response 404 (problem+json) if the SKU has no inventory row.

### PATCH /api/v1/inventory/{sku}
Adjusts the `on_hand` quantity for a SKU (Ops endpoint).

Request body: `{ "adjustment": 5 }` (positive = add stock, negative = remove stock)

Rules:
- `on_hand + adjustment` must remain >= `reserved` (invariant: `on_hand >= reserved`)
- `on_hand + adjustment` must remain >= 0

Response 200 with the updated inventory level.
Response 404 if SKU not found.
Response 422 (problem+json, type `invalid-adjustment`) if the adjustment violates the invariants.

---

## Files to create or modify

### Phase 1 — Production code

**1. Domain: add `adjust` method to `InventoryLevel` (`app/domain/inventory/entities.py`)**

Add a method `adjust(delta: int) -> None` that modifies `on_hand` by `delta`.
Raise `DomainError("invalid-adjustment", ...)` if the result would violate `on_hand >= reserved` or `on_hand >= 0`.

**2. Domain: add `get` to the port (`app/domain/inventory/ports.py`)**

Add a non-locking read method:
```python
async def get(self, sku: SKU) -> InventoryLevel: ...
```
Raise `DomainError("inventory-not-found", ...)` if missing.

**3. Infrastructure: implement `get` in `SqlAlchemyInventoryRepository` (`app/infrastructure/db/repositories/inventory.py`)**

Plain SELECT (no `with_for_update`). Raise `DomainError("inventory-not-found", ...)` if the row is absent.

**4. Application: create `app/application/get_inventory.py`**

`GetInventoryQuery(sku: str)` + `GetInventoryUseCase` that calls `uow.inventory.get(SKU(sku))` and returns the `InventoryLevel`.

**5. Application: create `app/application/adjust_inventory.py`**

`AdjustInventoryCommand(sku: str, adjustment: int)` + `AdjustInventoryUseCase` that:
- Calls `uow.inventory.get_for_update(SKU(sku))` (locking read inside transaction)
- Calls `level.adjust(cmd.adjustment)`
- Calls `uow.inventory.save(level)`
- Commits

**6. Interface schemas: create `app/interface/schemas/inventory.py`**

```python
class AdjustInventoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    adjustment: int

class InventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sku: str
    on_hand: int
    reserved: int
    available: int
```

**7. Interface router: create `app/interface/http/routers/inventory.py`**

Follow the same pattern as `app/interface/http/routers/products.py`.
- `GET /{sku}` → `GetInventoryUseCase` → `InventoryResponse`
- `PATCH /{sku}` → `AdjustInventoryUseCase` → `InventoryResponse`

**8. DI wiring: add to `app/interface/http/dependencies.py`**

Add `_get_get_inventory_use_case` and `_get_adjust_inventory_use_case` following the existing pattern.

**9. Register router in `app/interface/http/main.py`**

Add `from app.interface.http.routers.inventory import router as inventory_router` and `app.include_router(inventory_router)`.

**10. Add `InvalidAdjustmentError` to `app/domain/errors.py` if it does not exist.**

After all production code: run `uv run ruff check app && uv run ruff format --check app && uv run mypy app`. Fix all errors. Commit as `feat: inventory router GET and PATCH endpoints`.

---

### Phase 2 — Tests

Write tests in:
- `tests/unit/domain/test_inventory_adjust.py` — `adjust()` happy path, adjust below reserved, adjust below zero
- `tests/unit/application/test_get_inventory.py` — happy path, SKU not found
- `tests/unit/application/test_adjust_inventory.py` — happy path, invalid adjustment
- `tests/e2e/test_inventory_endpoints.py` — GET 200, GET 404, PATCH 200, PATCH 422

After writing all tests: run `uv run pytest -x -q`, then `uv run pytest tests/ --cov=app --cov-report=term-missing`.
Commit as `test: inventory router scenarios and edge cases`.
