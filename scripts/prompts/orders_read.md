# Task: Orders Read and State Transition Endpoints

Implement `GET /api/v1/orders/{id}`, `PATCH /api/v1/orders/{id}/cancel`, and `PATCH /api/v1/orders/{id}/confirm`.

You are working on the branch `feat/orders-get-patch` in its own git worktree.
This branch depends on the inventory router being present (the `cancel` and `confirm` transitions
touch inventory). The inventory router (`GET/PATCH /api/v1/inventory/{sku}`) is already merged
into `develop` before this branch was created — do not reimplement it.

Follow the hexagonal architecture described in `docs/ARCHITECTURE.md`.
Follow the quality rules in `docs/BEST_PRACTICES.md` and `.claude/rules/python.md`.

---

## What to build

### GET /api/v1/orders/{id}
Returns a single order with its lines.

Response 200:
```json
{ "id": "uuid", "status": "PENDING", "customer_id": null, "lines": [{"sku": "SKU-A", "quantity": 3}] }
```
Response 404 (problem+json, type `order-not-found`) if no order with that ID exists.

### PATCH /api/v1/orders/{id}/cancel
Cancels a PENDING order: releases all inventory reservations and sets status to CANCELLED.

Rules:
- Only PENDING orders can be cancelled.
- For each line: `inventory.release(line.quantity)` — releases the reservation.
- Status transitions to CANCELLED.

Response 200 with the updated order.
Response 404 if not found.
Response 409 (problem+json, type `invalid-state-transition`) if the order is not in PENDING state.

### PATCH /api/v1/orders/{id}/confirm
Confirms a PENDING order: converts reservations to committed decrements and sets status to CONFIRMED.

Rules:
- Only PENDING orders can be confirmed.
- For each line: `inventory.commit(line.quantity)` — decrements both `on_hand` and `reserved`.
- Status transitions to CONFIRMED.

Response 200 with the updated order.
Response 404 if not found.
Response 409 (problem+json, type `invalid-state-transition`) if the order is not in PENDING state.

---

## Files to create or modify

### Phase 1 — Production code

**1. Domain: add `cancel()` and `confirm()` to `Order` (`app/domain/orders/entities.py`)**

```python
def cancel(self) -> None:
    if self.status != OrderStatus.PENDING:
        raise InvalidStateTransitionError(self.id, self.status.value, "CANCELLED")
    self.status = OrderStatus.CANCELLED

def confirm(self) -> None:
    if self.status != OrderStatus.PENDING:
        raise InvalidStateTransitionError(self.id, self.status.value, "CONFIRMED")
    self.status = OrderStatus.CONFIRMED
```

**2. Add `InvalidStateTransitionError` and `OrderNotFoundError` to `app/domain/errors.py`.**

```python
class OrderNotFoundError(DomainError):
    problem_type = "order-not-found"
    http_status = 404
    def __init__(self, order_id: str) -> None:
        super().__init__("order-not-found", f"Order '{order_id}' not found.")
        self.order_id = order_id

class InvalidStateTransitionError(DomainError):
    problem_type = "invalid-state-transition"
    http_status = 409
    def __init__(self, order_id: str, current: str, target: str) -> None:
        super().__init__("invalid-state-transition",
                         f"Order '{order_id}' is in state {current}, cannot transition to {target}.")
        self.order_id = order_id
        self.current = current
        self.target = target
```

**3. Domain port: add `get_by_id` to `OrderRepository` (`app/domain/orders/ports.py`)**

```python
async def get_by_id(self, order_id: str) -> Order | None: ...
```

**4. Infrastructure: implement `get_by_id` in `SqlAlchemyOrderRepository` (`app/infrastructure/db/repositories/orders.py`)**

Query `OrderRow` by `id`, join/load `OrderLineRow`, reconstruct the `Order` domain object with its lines. Return `None` if not found.

**5. Application: create `app/application/get_order.py`**

`GetOrderQuery(order_id: str)` + `GetOrderUseCase` that calls `uow.orders.get_by_id(order_id)`, raises `OrderNotFoundError` if None.

**6. Application: create `app/application/cancel_order.py`**

`CancelOrderCommand(order_id: str)` + `CancelOrderUseCase` that inside a transaction:
- Loads the order (raises `OrderNotFoundError` if missing)
- Calls `order.cancel()`
- For each line: loads `inventory.get_for_update(line.sku)`, calls `level.release(line.quantity)`, saves
- Saves the order
- Commits

**7. Application: create `app/application/confirm_order.py`**

`ConfirmOrderCommand(order_id: str)` + `ConfirmOrderUseCase` that inside a transaction:
- Loads the order (raises `OrderNotFoundError` if missing)
- Calls `order.confirm()`
- For each line: loads `inventory.get_for_update(line.sku)`, calls `level.commit(line.quantity)`, saves
- Saves the order
- Commits

**8. Infrastructure: add `save` method to `SqlAlchemyOrderRepository`**

Updates the `status` of an existing `OrderRow` in the database.

**9. Domain port: add `save` to `OrderRepository` (`app/domain/orders/ports.py`)**

```python
async def save(self, order: Order) -> None: ...
```

**10. Interface schemas: no new schemas needed** — reuse `OrderResponse` from `app/interface/schemas/orders.py`.

**11. Interface router: add endpoints to `app/interface/http/routers/orders.py`**

- `GET /{order_id}` → `GetOrderUseCase`
- `PATCH /{order_id}/cancel` → `CancelOrderUseCase`
- `PATCH /{order_id}/confirm` → `ConfirmOrderUseCase`

Document 404 and 409 responses in each route.

**12. DI wiring: add the three new use cases to `app/interface/http/dependencies.py`.**

After all production code: run `uv run ruff check app && uv run ruff format --check app && uv run mypy app`. Fix all errors. Commit as `feat: GET /orders/{id} and cancel/confirm transitions`.

---

### Phase 2 — Tests

Write tests in:
- `tests/unit/domain/test_order_transitions.py` — cancel happy path, confirm happy path, cancel non-PENDING raises, confirm non-PENDING raises
- `tests/unit/application/test_get_order.py` — found, not found
- `tests/unit/application/test_cancel_order.py` — happy path (reservations released), order not found, invalid state
- `tests/unit/application/test_confirm_order.py` — happy path (inventory committed), order not found, invalid state
- `tests/e2e/test_orders_read.py` — GET 200, GET 404, PATCH cancel 200, PATCH cancel 409, PATCH confirm 200, PATCH confirm 409

After writing all tests: run `uv run pytest -x -q`, then `uv run pytest tests/ --cov=app --cov-report=term-missing`.
Commit as `test: orders read and state transition scenarios`.
