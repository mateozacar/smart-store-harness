# Python Ruleset — Mechanics

This file is the Python-specific enforcement layer for the Smart Store harness. It contains commands, config, and code templates the Dev subagent uses verbatim. Principles live in `docs/BEST_PRACTICES.md`; do not duplicate them here.

Detection: this file is loaded when `pyproject.toml` exists at the repository root. The `/build` skill rewrites the `@.claude/rules/*.md` line in `CLAUDE.md` before spawning the Dev subagent.

---

## 1. Toolchain (pinned)

| Tool | Version constraint | Purpose |
|---|---|---|
| Python | `>=3.12,<3.13` | Language runtime. |
| uv | latest | Dependency + venv manager. Never use `pip` directly. |
| ruff | `>=0.6` | Lint + format. Replaces black, isort, flake8. |
| mypy | `>=1.11` | Static typing, run with `--strict`. |
| pytest | `>=8` | Test runner. |
| pytest-asyncio | `>=0.23` | `asyncio_mode = "auto"`. |
| pytest-cov | `>=5` | Coverage. |
| testcontainers[postgres] | `>=4` | Real Postgres in integration tests. |
| httpx | `>=0.27` | Async HTTP client for e2e tests. |
| SQLAlchemy | `>=2.0` (imperative `Mapped[...]` style only) | ORM. |
| Alembic | `>=1.13` | Migrations. |
| FastAPI | `>=0.115` | Web framework. |
| Pydantic | `>=2.8` | DTOs and settings. |
| pydantic-settings | `>=2.4` | Env-driven config. |
| structlog | `>=24` | Structured logging. |

## 2. Commands the Agent Runs

The Dev subagent uses only these commands. Never `pip install`, never `python -m venv`.

```bash
# Environment setup (idempotent)
uv sync --frozen                    # install exact locked deps
uv sync                             # after adding a dep to pyproject.toml

# TDD loop
uv run pytest tests/unit/ -x -q                                 # unit tests, stop on first fail
uv run pytest tests/integration/ -x -q                          # integration (spawns testcontainer)
uv run pytest tests/ --cov=app --cov-report=term-missing        # full suite with coverage

# Quality gates (must all pass before opening PR)
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app

# Migrations
uv run alembic revision --autogenerate -m "<description>"
uv run alembic upgrade head
uv run alembic downgrade -1

# Local run
uv run uvicorn app.main:app --reload --port 8000
```

## 3. `pyproject.toml` (authoritative excerpt)

The subagent may add dependencies but must not weaken these settings.

```toml
[project]
name = "smart-store"
version = "0.1.0"
requires-python = ">=3.12,<3.13"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
  "E", "F", "W",       # pycodestyle + pyflakes
  "I",                  # isort
  "N",                  # pep8-naming
  "UP",                 # pyupgrade
  "B",                  # bugbear
  "SIM",                # simplify
  "RUF",                # ruff-specific
  "TID",                # tidy-imports (no relative imports across layers)
  "PL",                 # pylint subset
  "ASYNC",              # async-lint
]
ignore = ["PLR0913"]   # too-many-arguments; use kwargs discipline instead

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["PLR2004"]   # magic values allowed in tests

[tool.mypy]
python_version = "3.12"
strict = true
warn_unreachable = true
warn_return_any = true
disallow_any_explicit = true
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = ["testcontainers.*"]
ignore_missing_imports = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
markers = [
  "integration: requires a running Postgres testcontainer",
  "e2e: full HTTP round-trip",
]

[tool.coverage.run]
branch = true
source = ["app"]
omit = ["app/main.py", "app/interface/http/main.py"]

[tool.coverage.report]
fail_under = 85
show_missing = true
exclude_lines = ["pragma: no cover", "raise NotImplementedError"]

[tool.coverage.paths]
domain = ["app/domain"]
application = ["app/application"]

# Domain and application layers must hit 100%; enforced by CI script, not tool config.
```

## 4. Layer Enforcement (import rules)

Add a tidy-imports rule so `app/domain/` cannot import from framework or outer layers. This is enforced by ruff `TID` plus a dedicated CI check:

```bash
# scripts/check_layers.sh
set -euo pipefail
forbidden=$(grep -rnE '^(from|import) (fastapi|sqlalchemy|pydantic|httpx|app\.(infrastructure|interface))' app/domain/ || true)
if [ -n "$forbidden" ]; then
  echo "Layer violation in app/domain/:"; echo "$forbidden"; exit 1
fi
forbidden_app=$(grep -rnE '^(from|import) (fastapi|sqlalchemy|httpx|app\.(infrastructure|interface))' app/application/ || true)
if [ -n "$forbidden_app" ]; then
  echo "Layer violation in app/application/:"; echo "$forbidden_app"; exit 1
fi
```

The `review.yml` GitHub Action runs `scripts/check_layers.sh` as a step. A failure is a `BLOCKING` review finding.

## 5. Code Templates

Subagents copy these shapes when creating new domain concepts. Names change; structure does not.

### 5.1 Value object

```python
# app/domain/inventory/entities.py
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class SKU:
    value: str

    def __post_init__(self) -> None:
        if not self.value or len(self.value) > 32:
            raise DomainError("sku-invalid", "SKU must be 1..32 chars.")
        if not self.value.replace("-", "").isalnum():
            raise DomainError("sku-invalid", "SKU must be alphanumeric with dashes.")
```

Frozen + slots. Validation in `__post_init__`. No setters, no "update" methods.

### 5.2 Aggregate root

```python
# app/domain/inventory/entities.py
from dataclasses import dataclass, field
from app.domain.errors import DomainError

@dataclass
class InventoryLevel:
    sku: SKU
    on_hand: int
    reserved: int = 0

    def available(self) -> int:
        return self.on_hand - self.reserved

    def reserve(self, qty: int) -> None:
        if qty <= 0:
            raise DomainError("invalid-quantity", "Quantity must be positive.")
        if qty > self.available():
            raise InsufficientStock(self.sku, requested=qty, available=self.available())
        self.reserved += qty

    def release(self, qty: int) -> None:
        if qty <= 0 or qty > self.reserved:
            raise DomainError("invalid-release", "Cannot release more than reserved.")
        self.reserved -= qty

    def commit(self, qty: int) -> None:
        if qty <= 0 or qty > self.reserved:
            raise DomainError("invalid-commit", "Cannot commit more than reserved.")
        self.reserved -= qty
        self.on_hand -= qty
```

Public methods only. No external mutation of `reserved` or `on_hand`.

### 5.3 Domain error

```python
# app/domain/errors.py
from dataclasses import dataclass

class DomainError(Exception):
    problem_type: str = "domain-error"
    http_status: int = 422
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

@dataclass
class InsufficientStock(DomainError):
    problem_type = "insufficient-stock"
    http_status = 409
    def __init__(self, sku: "SKU", requested: int, available: int) -> None:
        super().__init__("insufficient-stock", f"Requested {requested}, available {available}.")
        self.sku = sku.value
        self.requested = requested
        self.available = available
```

Each subclass declares `problem_type` and `http_status`. The HTTP mapper (`app/interface/http/errors.py`) reads these; no interface code hardcodes status codes.

### 5.4 Port (Protocol)

```python
# app/domain/inventory/ports.py
from typing import Protocol
from app.domain.inventory.entities import InventoryLevel, SKU

class InventoryRepository(Protocol):
    async def get_for_update(self, sku: SKU) -> InventoryLevel: ...
    async def save(self, level: InventoryLevel) -> None: ...
```

`Protocol`, not `ABC`. Async signatures. No implementation in the domain layer.

### 5.5 Application use case

```python
# app/application/place_order.py
from dataclasses import dataclass
from app.application.unit_of_work import UnitOfWork
from app.domain.orders.entities import Order, OrderLine
from app.domain.inventory.entities import SKU

@dataclass(frozen=True)
class PlaceOrderCommand:
    customer_id: str | None
    lines: tuple[tuple[str, int], ...]   # (sku, quantity)

class PlaceOrderUseCase:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: PlaceOrderCommand) -> Order:
        async with self._uow:
            order = Order.new(customer_id=cmd.customer_id)
            for sku_str, qty in cmd.lines:
                sku = SKU(sku_str)
                level = await self._uow.inventory.get_for_update(sku)
                level.reserve(qty)
                await self._uow.inventory.save(level)
                order.add_line(OrderLine(sku=sku, quantity=qty))
            await self._uow.orders.add(order)
            await self._uow.commit()
            return order
```

Use case orchestrates domain + ports. Never imports SQLAlchemy or FastAPI. Transactions are the `UnitOfWork` context manager, not a decorator.

### 5.6 SQLAlchemy repository (infrastructure)

```python
# app/infrastructure/db/repositories/inventory.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.inventory.entities import InventoryLevel, SKU
from app.infrastructure.db.models import InventoryRow

class SqlAlchemyInventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_update(self, sku: SKU) -> InventoryLevel:
        stmt = select(InventoryRow).where(InventoryRow.sku == sku.value).with_for_update()
        row = (await self._session.execute(stmt)).scalar_one()
        return InventoryLevel(sku=SKU(row.sku), on_hand=row.on_hand, reserved=row.reserved)

    async def save(self, level: InventoryLevel) -> None:
        stmt = select(InventoryRow).where(InventoryRow.sku == level.sku.value)
        row = (await self._session.execute(stmt)).scalar_one()
        row.on_hand = level.on_hand
        row.reserved = level.reserved
```

`with_for_update()` is mandatory on any read inside a reservation flow. The repository translates between ORM rows and domain entities; the two never leak into each other.

### 5.7 Unit test (unit layer, fake repo)

```python
# tests/unit/application/test_place_order.py
import pytest
from app.application.place_order import PlaceOrderCommand, PlaceOrderUseCase
from app.domain.errors import InsufficientStock
from tests.unit.fakes import FakeUnitOfWork

async def test_reserves_inventory_on_order_creation() -> None:
    uow = FakeUnitOfWork.with_stock({"SKU-A": (on_hand := 10, reserved := 0)})
    use_case = PlaceOrderUseCase(uow)

    order = await use_case.execute(PlaceOrderCommand(customer_id=None, lines=(("SKU-A", 3),)))

    assert order.status.value == "PENDING"
    level = uow.inventory.state["SKU-A"]
    assert level.reserved == 3
    assert level.on_hand == 10

async def test_rejects_order_when_stock_insufficient() -> None:
    uow = FakeUnitOfWork.with_stock({"SKU-B": (2, 1)})
    use_case = PlaceOrderUseCase(uow)

    with pytest.raises(InsufficientStock) as exc:
        await use_case.execute(PlaceOrderCommand(customer_id=None, lines=(("SKU-B", 2),)))

    assert exc.value.available == 1
    assert uow.committed is False
```

Fakes live under `tests/unit/fakes.py`. Never mock domain services or use cases; use the real ones with fake ports.

### 5.8 Integration test (real Postgres)

```python
# tests/integration/test_reservation_concurrency.py
import asyncio
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

pytestmark = pytest.mark.integration

async def test_concurrent_orders_do_not_double_book(pg_session_factory: async_sessionmaker) -> None:
    await seed_inventory(pg_session_factory, sku="SKU-C", on_hand=1)

    async def place_one() -> bool:
        try:
            await run_use_case(pg_session_factory, sku="SKU-C", qty=1)
            return True
        except InsufficientStock:
            return False

    results = await asyncio.gather(place_one(), place_one())
    assert sorted(results) == [False, True]
    level = await fetch_level(pg_session_factory, "SKU-C")
    assert level.reserved == 1
```

The `pg_session_factory` fixture is a session-scoped testcontainer Postgres. Migrations run once at container start.

### 5.9 Testcontainer fixture

```python
# tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from alembic import command
from alembic.config import Config

@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
async def pg_session_factory(postgres_container):
    dsn = postgres_container.get_connection_url().replace("psycopg2", "psycopg")
    engine = create_async_engine(dsn.replace("postgresql", "postgresql+psycopg"))
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", dsn)
    command.upgrade(cfg, "head")
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
```

Container is session-scoped (starts once per test run). Migrations run against it at startup.

## 6. Implementation + Test Contract

The subagent writes all production code first, then writes all tests in a single pass at the end.

**Phase 1 — Implement all production code (no pytest calls)**

1. Write domain entities, value objects, and domain errors.
2. Write application use cases.
3. Write infrastructure adapters (repositories, unit of work, SQLAlchemy models).
4. Write the interface layer (routes, schemas, error handler wiring).
5. After each layer: `uv run ruff check app && uv run ruff format app && uv run mypy app` — must be clean before moving to the next layer.
6. Commit: `feat: <description>`.

**Phase 2 — Write all tests (after all code and migrations exist)**

Write every required test in one pass, then run:

1. Every Gherkin scenario at the layer(s) from the Test Matrix (mandatory, no exceptions).
2. Happy-path tests for each use case / endpoint not already covered by the Gherkin scenarios.
3. Edge-case tests: invalid inputs, boundary conditions, missing fields, conflict states.

Layer placement:
- `unit` → `tests/unit/` (pure Python, no I/O)
- `integration` → `tests/integration/` (testcontainer Postgres)
- `e2e` → `tests/e2e/` (full FastAPI + testcontainer via `httpx.AsyncClient`)

After writing all tests:

```bash
uv run pytest -x -q                                              # stop on first failure; fix and re-run until green
uv run pytest tests/ --cov=app --cov-report=term-missing        # full suite with coverage; must pass --cov-fail-under=85
uv run ruff check app tests && uv run ruff format app tests && uv run mypy app
```

Commit: `test: scenarios + edge cases for #<issue-number>`.

## 7. Async Discipline

- Every I/O function is `async def`. Blocking calls (`time.sleep`, `requests`, `open` on hot paths) are forbidden outside setup scripts.
- FastAPI route handlers are `async def`.
- SQLAlchemy sessions are `AsyncSession`; engines are `create_async_engine`.
- `pytest-asyncio` is in `auto` mode — do not decorate tests with `@pytest.mark.asyncio`.
- Never mix `asyncio.run()` and pytest-asyncio; the fixture manages the loop.

## 8. Common Pitfalls (agent must avoid)

- **`Mapped[int]` vs plain `int` in SQLAlchemy models.** Use `Mapped[int] = mapped_column(...)`. Plain annotations break the 2.0 typing.
- **Pydantic v1 syntax.** No `class Config:`; use `model_config = ConfigDict(extra="forbid")`.
- **`datetime.utcnow()`.** Deprecated in 3.12. Use `datetime.now(timezone.utc)`.
- **`Optional[X]`.** Use `X | None` (Python 3.12).
- **Relative imports across layers.** Ruff `TID` blocks these; use absolute imports (`from app.domain...`).
- **Autoflush surprises.** Sessions are created with `autoflush=False` in this project. Explicit `await session.flush()` when the test needs to observe writes before commit.
- **Testcontainer leakage.** The session-scoped fixture is required; per-test containers add ~5s each and blow the demo timing.

## 9. Migration Discipline

- Every model change → `uv run alembic revision --autogenerate -m "<verb>_<what>"`.
- Review the generated file before committing. Autogenerate misses `CHECK` constraints and some index changes; add them by hand.
- The reservation column migration must include:
  ```python
  op.add_column("inventory", sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"))
  op.create_check_constraint("ck_inventory_reserved_nonneg", "inventory", "reserved >= 0")
  op.create_check_constraint("ck_inventory_on_hand_ge_reserved", "inventory", "on_hand >= reserved")
  ```
- Down migrations drop constraints and columns in reverse order.

## 10. Directory Skeleton the Agent Creates on First Story

If `app/` does not yet exist, the subagent creates this exact skeleton before writing any test, then commits it as `chore: scaffold hexagonal layout` in a first commit on the feature branch. Subsequent commits carry the story's actual work.

```
app/
├── __init__.py
├── main.py
├── domain/
│   ├── __init__.py
│   ├── errors.py
│   ├── products/__init__.py
│   ├── inventory/__init__.py
│   ├── orders/__init__.py
│   └── customers/__init__.py
├── application/
│   ├── __init__.py
│   └── unit_of_work.py
├── infrastructure/
│   ├── __init__.py
│   ├── config.py
│   └── db/
│       ├── __init__.py
│       ├── session.py
│       ├── models.py
│       └── repositories/__init__.py
└── interface/
    ├── __init__.py
    └── http/
        ├── __init__.py
        ├── main.py
        ├── errors.py
        ├── dependencies.py
        ├── routers/__init__.py
        └── schemas/__init__.py

tests/
├── __init__.py
├── conftest.py
├── unit/__init__.py
├── integration/__init__.py
└── e2e/__init__.py
```

Every subfolder gets an `__init__.py`. Never a `src/` layout — the tree matches `docs/ARCHITECTURE.md §2` exactly.
