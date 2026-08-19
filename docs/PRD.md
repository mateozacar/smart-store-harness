# Smart Store API — Product Requirements Document

Owner: Presenter
Status: Living document. Update via user instruction only; agents must not edit this file autonomously.

---

## 1. Mission

A minimal, correct commerce API that serves as the substrate for a near-autonomous Claude Code delivery harness. The product must be small enough to fit in a talk and rich enough to exhibit real transactional constraints (inventory reservation on order creation). Every feature added on stage must be delivered end-to-end by the harness: story → branch → TDD implementation → PR → automated review → deploy.

## 2. Personas

- **Buyer** — end customer who places orders; consumes the public API.
- **Ops** — operations user who manages inventory levels and monitors orders.
- **Admin** — internal role used only for seeding and demo control.

## 3. Resources & Invariants

Each resource is exposed under `/api/v1/<resource>`. The invariants below are load-bearing: every story that touches a resource must preserve them, and the Dev subagent must derive test cases from them.

### `/products`
Catalog items available for sale.
- `sku` is unique and immutable once created.
- `price` is a non-negative decimal with two fractional digits.
- A product cannot be deleted while referenced by any order in state `PENDING` or `CONFIRMED`.

### `/inventory`
Stock levels per SKU. One row per SKU in v1 (no multi-warehouse yet).
- `on_hand >= 0`.
- `reserved >= 0`.
- `on_hand >= reserved` at all times.
- `available` is a derived value (`on_hand - reserved`); never stored, always computed at read time.

### `/orders`
Customer orders with line items referencing products.
- Order states: `PENDING` → `CONFIRMED` → `FULFILLED`, or `PENDING` → `CANCELLED`.
- Every line item quantity is strictly greater than zero.
- An order in `PENDING` state holds reservations equal to the sum of its line items per SKU.
- Transitioning to `CONFIRMED` converts reservations to committed decrements: `on_hand -= qty`, `reserved -= qty`.
- Transitioning to `CANCELLED` releases reservations: `reserved -= qty`, `on_hand` unchanged.

### `/customers`
Buyers registered in the system.
- `email` is unique and stored lowercase.
- `email` matches RFC 5322 basic form.

## 4. Backlog — Story 1 (initial delivery, in scope for the first demo run)

**Title:** Add inventory reservation when creating an order.

**As a** Buyer
**I want** each order I place to reserve the requested inventory atomically
**So that** I do not receive a confirmation for items that are already sold out.

**Constraints**
- Always: reservation writes and order writes happen inside a single database transaction.
- Always: the transaction acquires a row-level lock on each affected inventory row before checking availability.
- Block If: any line item quantity exceeds current available (`on_hand - reserved`) for that SKU.
- Never: allow negative `available`, negative `reserved`, or partial reservations.

**Acceptance Criteria**

```gherkin
Scenario: Order created when stock is available
  Given product SKU "SKU-A" has on_hand=10 and reserved=0
  When a Buyer creates an order for 3 units of "SKU-A"
  Then the API responds 201 with the created order
   And the order is persisted in state PENDING
   And inventory for "SKU-A" shows reserved=3
   And inventory for "SKU-A" shows on_hand unchanged at 10

Scenario: Order rejected when stock insufficient
  Given product SKU "SKU-B" has on_hand=2 and reserved=1
  When a Buyer requests an order for 2 units of "SKU-B"
  Then the API responds 409 with a problem+json body of type "insufficient-stock"
   And no order row is persisted
   And no reservation change is persisted

Scenario: Concurrent orders do not double-book
  Given product SKU "SKU-C" has on_hand=1 and reserved=0
  When two Buyers submit orders for 1 unit of "SKU-C" concurrently
  Then exactly one order succeeds with 201
   And the other receives 409 insufficient stock
   And reserved for "SKU-C" ends at 1, never 2
```

**Definition of Done**
- [ ] Domain unit tests cover all three scenarios (pure, no I/O).
- [ ] Integration test with real Postgres validates the concurrent scenario using `SELECT ... FOR UPDATE`.
- [ ] `POST /api/v1/orders` documented in the OpenAPI schema, including the 409 response body.
- [ ] Alembic migration adds `reserved` column with default 0 and a `CHECK (reserved >= 0 AND on_hand >= reserved)` constraint.
- [ ] CHANGELOG entry under `[Unreleased]`.

## 5. Demo Backlog (candidates for live additions on stage)

Stories the presenter can inject during the talk with `/story "<one-liner>"`. Ordered from smallest to largest so the harness runtime stays predictable on stage.

**Features**
1. Release reservation when an order is cancelled.
2. Confirm an order: convert reservation to committed decrement.
3. List products with pagination (`page`, `size`, `sort=created_at.desc`).
4. Search products by partial name, case-insensitive.
5. Attach a customer to an order at creation time.
6. Expose derived `available` on `GET /api/v1/products/{sku}`.
7. Idempotency-Key header on `POST /api/v1/orders` to make retries safe.

**Bugs (planted intentionally, to be fixed live by the harness)**
1. `POST /api/v1/customers` accepts duplicate emails when case differs (`ada@x.com` vs `Ada@x.com`).
2. `POST /api/v1/orders` accepts a line item with `quantity=0`.
3. When order creation fails after the reservation write, the reservation is not released (missing rollback).

Each bug should be filed as a GitHub issue with a failing regression test in the acceptance criteria — the harness fixes it by writing that test first, then the code.

## 6. Non-Goals (v1)

- Payment processing.
- Shipping and fulfillment.
- Discounts, promotions, taxes.
- Multi-currency.
- Authentication and authorization (candidate for a later story if time permits).
- Multi-tenant isolation.
- Event streaming / webhooks.
- Search relevance beyond `ILIKE` on product name.

## 7. Success Metrics (for the harness demo)

- Time from `/story` invocation to a green PR check: under 8 minutes end-to-end.
- Time from PR merge to Render staging returning 200 on `/healthz`: under 3 minutes.
- Percentage of demo stories that reach `main` with no human code edits: tracked across the talk; target ≥ 80%.
- Percentage of Claude Code Review comments that are actionable (not noise): reviewed after the talk; target ≥ 70%.
