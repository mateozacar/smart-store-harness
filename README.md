# Smart Store API

A minimal, correct commerce API serving as the substrate for a near-autonomous Claude Code delivery harness.

## Run locally

### Prerequisites

- Docker (or colima)
- [uv](https://docs.astral.sh/uv/) package manager
- Python 3.12

### Steps

1. Start Postgres:

```bash
docker-compose up -d
```

2. Install dependencies:

```bash
uv sync
```

3. Run database migrations:

```bash
uv run alembic upgrade head
```

4. Start the API server:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

The API is available at http://localhost:8000. OpenAPI docs at http://localhost:8000/docs.

### Run tests

```bash
# Unit tests (no DB required)
uv run pytest tests/unit/ -x -q

# Integration tests (requires Docker)
uv run pytest tests/integration/ -x -q

# E2E tests (requires Docker)
uv run pytest tests/e2e/ -x -q

# Full suite with coverage
uv run pytest --cov=app --cov-report=term-missing
```

### Quality gates

```bash
uv run ruff check app tests
uv run ruff format app tests
uv run mypy app
bash scripts/check_layers.sh
```
