# Smart Store API — Architecture

Owner: Presenter
Status: Living document. Update via user instruction only; agents must not edit this file autonomously.

---

## 1. Stack

| Concern | Choice | Version | Rationale |
|---|---|---|---|
| Language | Python | 3.12 | Type hints + PEP 695; matches team ruleset. |
| Web framework | FastAPI | ≥ 0.115 | Async, native OpenAPI, dependency injection. |
| ORM | SQLAlchemy | 2.0 (imperative style) | Explicit transactions, `SELECT ... FOR UPDATE`. |
| Migrations | Alembic | ≥ 1.13 | Deterministic schema history. |
| Database | PostgreSQL | 16 | Real transactions, row-level locks, `CHECK` constraints. |
| Validation | Pydantic | v2 | DTO layer at the interface boundary. |
| Tests | pytest + pytest-asyncio + testcontainers | latest | Real Postgres in integration tests, no ORM mocks. |
| Lint / format | Ruff | latest | Single tool for lint + format. |
| Type check | mypy `--strict` | latest | Enforced in CI. |
| Runtime | uvicorn | latest | ASGI server on Render. |
| Package management | uv | latest | Fast, reproducible lockfile. |

## 2. Layered Structure (Hexagonal / Ports & Adapters)

The codebase is split into four layers. Dependencies point inward only: **interface → application → domain**, with **infrastructure** implementing ports declared by the domain. Framework imports (FastAPI, SQLAlchemy) are forbidden inside `app/domain/`.

```
app/
├── domain/                      # Pure business rules. No I/O, no framework imports.
│   ├── products/
│   │   ├── entities.py          # Product entity, value objects (SKU, Price).
│   │   └── errors.py            # DomainError subclasses.
│   ├── inventory/
│   │   ├── entities.py          # InventoryLevel aggregate.
│   │   ├── services.py          # ReserveInventory domain service.
│   │   └── ports.py             # InventoryRepository Protocol.
│   ├── orders/
│   │   ├── entities.py          # Order aggregate, OrderLine value object.
│   │   ├── services.py          # PlaceOrder domain service (uses InventoryRepository port).
│   │   └── ports.py             # OrderRepository Protocol.
│   └── customers/
│       ├── entities.py
│       └── ports.py
├── application/                 # Use cases. Orchestrates domain + ports. Still framework-free.
│   ├── place_order.py           # PlaceOrderUseCase — the reservation story lives here.
│   ├── cancel_order.py
│   └── unit_of_work.py          # UnitOfWork Protocol; commit/rollback boundary.
├── infrastructure/              # Adapters. All framework and DB code lives here.
│   ├── db/
│   │   ├── models.py            # SQLAlchemy ORM classes (separate from domain entities).
│   │   ├── session.py           # engine, session factory.
│   │   ├── unit_of_work.py      # SqlAlchemyUnitOfWork implementing the application port.
│   │   └── repositories/
│   │       ├── inventory.py     # SqlAlchemyInventoryRepository (implements domain port).
│   │       ├── orders.py
│   │       ├── products.py
│   │       └── customers.py
│   └── config.py                # Pydantic Settings (env-driven).
├── interface/                   # HTTP layer. Pydantic DTOs, routers, error handlers.
│   ├── http/
│   │   ├── main.py              # FastAPI app factory.
│   │   ├── dependencies.py      # DI wiring: use cases + unit of work.
│   │   ├── errors.py            # DomainError → RFC 7807 problem+json mapper.
│   │   └── routers/
│   │       ├── products.py
│   │       ├── inventory.py
│   │       ├── orders.py
│   │       └── customers.py
│   └── schemas/                 # Pydantic request/response models.
└── main.py                      # ASGI entrypoint for uvicorn.

tests/
├── unit/                        # Fast, in-memory, no DB. Test domain and application in isolation.
├── integration/                 # Real Postgres via testcontainers. Test infrastructure adapters.
└── e2e/                         # Full HTTP round-trip via httpx.AsyncClient.

alembic/
├── env.py
└── versions/                    # One file per migration.
```

**Rule:** if a file under `app/domain/` imports `fastapi`, `sqlalchemy`, `pydantic`, `httpx`, or anything from `app/infrastructure/` / `app/interface/`, the Dev subagent must reject the change.

## 3. Domain Model

```
Product (aggregate root)
  - sku: SKU (value object)
  - name: str
  - price: Price (value object, non-negative Decimal)

InventoryLevel (aggregate root, keyed by SKU)
  - sku: SKU
  - on_hand: int
  - reserved: int
  - available() -> int           # derived, never persisted
  - reserve(qty: int) -> None    # raises InsufficientStock if qty > available()
  - release(qty: int) -> None
  - commit(qty: int) -> None     # on_hand -= qty, reserved -= qty

Customer (aggregate root)
  - id: UUID
  - email: Email (value object, normalized lowercase)

Order (aggregate root)
  - id: UUID
  - customer_id: UUID | None     # nullable until "attach customer" story lands
  - lines: list[OrderLine]       # non-empty
  - status: OrderStatus          # PENDING | CONFIRMED | FULFILLED | CANCELLED

OrderLine (value object, immutable)
  - sku: SKU
  - quantity: int                # > 0
```

Value objects (`SKU`, `Price`, `Email`) enforce their invariants in `__init__`. Constructing an invalid value object raises `DomainError`. There is no "validate later" path.

## 4. Transaction Boundary (Reservation Flow)

The reservation story is the reason Postgres is not swappable for SQLite in this demo. The sequence must hold under concurrency.

```
Client                Interface (FastAPI)       Application               Infrastructure          Postgres
  |                          |                       |                          |                    |
  | POST /orders             |                       |                          |                    |
  |------------------------->|                       |                          |                    |
  |                          | validate DTO          |                          |                    |
  |                          | resolve PlaceOrder    |                          |                    |
  |                          |---------------------->|                          |                    |
  |                          |                       | uow.begin()              |                    |
  |                          |                       |------------------------->|                    |
  |                          |                       |                          | BEGIN              |
  |                          |                       |                          |------------------->|
  |                          |                       | for each line:           |                    |
  |                          |                       |   inv = inv_repo.get_for_update(sku)          |
  |                          |                       |------------------------->|                    |
  |                          |                       |                          | SELECT ... FOR UPDATE
  |                          |                       |                          |------------------->|
  |                          |                       |   inv.reserve(qty)       |                    |
  |                          |                       |   inv_repo.save(inv)     |                    |
  |                          |                       |------------------------->|                    |
  |                          |                       |                          | UPDATE inventory   |
  |                          |                       |                          |------------------->|
  |                          |                       | order_repo.add(order)    |                    |
  |                          |                       |------------------------->|                    |
  |                          |                       |                          | INSERT INTO orders |
  |                          |                       |                          |------------------->|
  |                          |                       | uow.commit()             |                    |
  |                          |                       |------------------------->|                    |
  |                          |                       |                          | COMMIT             |
  |                          |                       |                          |------------------->|
  |                          |<----------------------|                          |                    |
  |<-------------------------|                       |                          |                    |
  |    201 Created           |                       |                          |                    |
```

If any step raises (`InsufficientStock`, DB error), the `UnitOfWork` context manager rolls back. No partial state escapes the boundary.

## 5. API Contract Summary

Base path: `/api/v1`. All responses are JSON. Errors use RFC 7807 `application/problem+json`.

| Method | Path | Description | Success | Notable errors |
|---|---|---|---|---|
| GET | `/products` | List products (paginated later). | 200 | — |
| GET | `/products/{sku}` | Get one product. | 200 | 404 not-found |
| POST | `/products` | Create product. | 201 | 409 sku-conflict |
| GET | `/inventory/{sku}` | Get inventory level. | 200 | 404 not-found |
| PATCH | `/inventory/{sku}` | Adjust `on_hand` (Ops only, no auth in v1). | 200 | 422 invalid-adjustment |
| POST | `/orders` | Create order with lines; reserves inventory. | 201 | 409 insufficient-stock, 422 invalid-order |
| GET | `/orders/{id}` | Get one order. | 200 | 404 not-found |
| POST | `/customers` | Register customer. | 201 | 409 email-conflict |
| GET | `/healthz` | Liveness probe (returns "ok"). | 200 | — |

## 6. Error Model

All errors are surfaced as RFC 7807. Domain errors map 1:1 to problem types.

```json
{
  "type": "https://smart-store.example/problems/insufficient-stock",
  "title": "Insufficient stock",
  "status": 409,
  "detail": "Requested 5 units of SKU-A but only 2 available.",
  "sku": "SKU-A",
  "requested": 5,
  "available": 2
}
```

`DomainError` subclasses declare their `problem_type`, HTTP status, and machine-readable fields. The mapper in `interface/http/errors.py` translates them; no `HTTPException` is raised outside that layer.

## 7. Configuration

All configuration is read from environment variables via `pydantic-settings`. Nothing is hardcoded in code paths.

| Variable | Example | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/smart_store` | Postgres DSN. |
| `APP_ENV` | `development` / `staging` / `production` | Runtime context. |
| `LOG_LEVEL` | `INFO` | Root log level. |
| `CORS_ORIGINS` | `https://demo.example` | Comma-separated origins. |

## 8. Deployment Topology (Render)

Two Render web services + one Render Postgres instance per environment.

```
GitHub main ─── deploy-prod.yml ────► POST /v1/services/<prod-id>/deploys ─► smart-store-prod  ─► Render Postgres (prod)
GitHub develop ── autoDeploy (render.yaml) ─────────────────────────────────► smart-store-staging ─► Render Postgres (staging)
```

- Staging deploys automatically on every push to `develop` via `render.yaml` `autoDeployTrigger: commit`.
- Production deploys via GitHub Actions with `environment: production` (required reviewer gate), calling the Render Deploy API.
- Database migrations run as a Render **pre-deploy command**: `alembic upgrade head`.
- `/healthz` is the Render health check path.
- Cold start mitigation: paid plan for the demo services; a pre-warm cron every 14 minutes on the free plan alternative.

## 9. Observability

- Structured logs (JSON) via `structlog`, correlated by a per-request `request_id` middleware.
- Metrics deferred to a later story (Prometheus endpoint on `/metrics` if added).
- Errors logged at `ERROR` level with the problem type and stack trace; 4xx client errors logged at `INFO`.

## 10. Non-Architecture (explicit exclusions v1)

- No service mesh, no gRPC, no message broker.
- No caching layer (`GET /products` hits the DB directly).
- No feature flags.
- No async task queue.

Adding any of these is a PRD change, not a technical decision.
