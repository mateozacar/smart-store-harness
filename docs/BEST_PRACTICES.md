# Smart Store API — Engineering Best Practices

Owner: Presenter
Status: Living document. Update via user instruction only; agents must not edit this file autonomously.

This document is the quality bar every subagent must clear. It states principles; the language-specific enforcement mechanics (test runners, lint config, folder rules) live in `.claude/rules/<language>.md`, loaded automatically by the `/build` skill.

---

## 1. TDD is Mandatory

Red → green → refactor. Not aspirational, not "when convenient." A Dev subagent must:

1. Read the story's Gherkin scenarios.
2. Write a failing test that maps to the first scenario.
3. Run the test and observe it fail for the *right reason* (not an import error).
4. Write the minimum code to make it pass.
5. Run the test and observe it pass.
6. Refactor with the test still green.
7. Move to the next scenario.

**Forbidden:** writing production code before a corresponding failing test exists. If the subagent finds itself about to edit a file under `app/` without a test in `tests/` demanding the change, it stops and writes the test first.

**Test naming:** describe behavior, not implementation. `test_rejects_order_when_stock_insufficient`, not `test_place_order_raises`.

## 2. Domain-Driven Design, Lightweight

We use the DDD tactical patterns that pay for themselves in a small codebase and skip the ceremony that does not.

**Adopt:**
- **Aggregates** with a single root that guards invariants. `InventoryLevel` owns the `reserve/release/commit` rules; no external caller can mutate `reserved` directly.
- **Value objects** for concepts with equality-by-value: `SKU`, `Price`, `Email`. Immutable, self-validating in `__init__`.
- **Ports (Protocols) and adapters.** Domain code depends on abstractions; concrete SQLAlchemy repositories implement them in `app/infrastructure/`.
- **Domain services** for logic that spans aggregates (`PlaceOrder` needs both `Order` and `InventoryLevel`).
- **Ubiquitous language.** Names in code match names in `docs/PRD.md`. If the PRD says "reserve," the method is `reserve()`, not `hold()` or `book()`.

**Skip:**
- Bounded contexts and context maps (one context in v1).
- Event sourcing.
- CQRS.
- Domain events (may return later if audit requirements arrive).

## 3. Clean Code, the Rules That Matter

Not the whole book. These are the rules the review action enforces:

- **Functions do one thing.** If the name has "and" or a comment explains a section, split it.
- **Names describe intent.** `reserve_inventory` not `handle_inv`; `insufficient_stock` not `err`.
- **No comments explaining *what*.** Code shows what. Comments explain *why*, and only when the why is non-obvious (a workaround, a subtle invariant).
- **Prefer immutability.** Value objects are frozen. Aggregates mutate through methods, never via attribute assignment from outside.
- **No dead code, no `TODO` left behind.** If it is not done, it is not merged.
- **No abbreviations except industry-standard ones** (`sku`, `id`, `url` are fine; `qty` is fine because it appears in the PRD; `usr` is not).
- **Depth limits:** functions ≤ 20 lines is the target, ≤ 40 is the ceiling; nesting ≤ 3 levels; cyclomatic complexity ≤ 8.

## 4. Testing Standards

- **Unit tests** live in `tests/unit/`, run in milliseconds, touch no I/O, no database, no HTTP. They test domain entities, value objects, domain services, and application use cases with fake repositories.
- **Integration tests** live in `tests/integration/`, run against a real Postgres launched by testcontainers. They test infrastructure adapters (repositories, unit of work) and any concurrent behavior (like the reservation race).
- **End-to-end tests** live in `tests/e2e/`, drive the full FastAPI app via `httpx.AsyncClient` against a testcontainer DB. One happy-path test per endpoint, plus edge cases the PRD calls out.
- **No mocking of the ORM or the DB.** Mocking these produces green tests that lie. Use real Postgres via testcontainers for anything that touches a repository.
- **Coverage floor:** 85% overall, 100% on `app/domain/` and `app/application/`. Coverage is a floor, not a goal; passing tests that cover the wrong things is worse than lower coverage.
- **Fixtures over setup/teardown classes.** Fixtures compose; classes do not.
- **One assertion concept per test.** Multiple `assert` lines are fine if they describe the same behavior; write a new test for a new behavior.

## 5. API Design Conventions

- **Nouns for resources**, plural, lowercase-kebab where multi-word: `/order-lines`, not `/orderLines`.
- **HTTP methods carry meaning.** `POST` creates, `PUT` full-replaces, `PATCH` partial-updates, `DELETE` deletes. `GET` never mutates.
- **Status codes are informative.** `201` on create with a `Location` header. `409` for conflict (already exists, insufficient stock). `422` for well-formed but semantically invalid payloads. `500` only for truly unexpected server errors.
- **Errors are RFC 7807 problem+json.** Every domain error maps to a stable `type` URI documented in `docs/ARCHITECTURE.md` §6.
- **Idempotency.** Any endpoint that a client may retry must accept an `Idempotency-Key` header once that story lands.
- **Versioning.** All routes live under `/api/v1`. Breaking changes bump the prefix; additive changes do not.

## 6. Errors, Logs, and Boundaries

- **Never catch `Exception` broadly.** Catch specific exceptions or let them propagate to the interface error handler.
- **Domain layer raises `DomainError` subclasses only.** No `HTTPException`, no framework exceptions.
- **Infrastructure translates driver errors** (e.g., `IntegrityError`) into domain errors (`SkuConflict`) at the repository boundary.
- **Log at boundaries, not everywhere.** A single structured log entry per request, plus errors. No `print`, no `logging.debug` scattered in domain code.
- **Correlation:** every request generates a `request_id`; it appears in every log line for that request.

## 7. Database & Migrations

- **Every schema change is an Alembic migration** in `alembic/versions/`. Never edit the DB by hand.
- **Migrations are reversible when reasonable.** Down migrations may be a no-op only for irreversible changes (data destruction), and this is documented in the migration file.
- **Constraints belong in the database.** `NOT NULL`, `UNIQUE`, `CHECK (on_hand >= reserved)`. Do not enforce in Python what the DB can enforce.
- **Indexes are explicit,** added in the same migration that introduces the query pattern requiring them.
- **Transactions are explicit,** managed by `UnitOfWork`. No implicit autocommit in application code.

## 8. Security Baseline (v1)

- **Never log secrets, tokens, PII.** Emails are considered PII; log the customer ID instead.
- **Parametrize all queries.** SQLAlchemy handles this by default; raw SQL is banned outside migrations.
- **Reject unknown fields.** Pydantic models use `model_config = ConfigDict(extra="forbid")`.
- **CORS is explicit.** No `allow_origins=["*"]` in production.
- **Dependencies are pinned** via `uv.lock`; `uv sync --frozen` in CI.
- **Secrets come from env vars only.** Never committed, never in code, never in logs.

## 9. Git, Branches, and PRs

- **Gitflow:** `feature/<issue>-<slug>` → `develop`; `release/*` for release cuts; `main` is prod.
- **Branch created via `gh issue develop <n>`** so the PR auto-links to the issue.
- **Commit messages** follow Conventional Commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **One story per branch.** No mixed concerns.
- **PR body** references the issue with `Closes #<n>`, lists what changed, notes any deviation from the story.
- **The PR is opened by the `/build` skill**, never by hand during a demo run.
- **Merges to `develop` are squash-merges;** merges to `main` are merge commits (preserve staging history).

## 10. What the Code Review Action Enforces

`.github/workflows/review.yml` runs Claude Code review on every PR. Its custom instructions cite this document. A finding is `BLOCKING` when:

- Any file under `app/domain/` imports a framework module.
- Production code was added without a corresponding test in the diff.
- A migration is missing for a model change.
- Coverage drops below the thresholds in §4.
- An endpoint returns a raw string or non-problem+json error body.
- `except Exception:` appears anywhere outside `app/interface/http/errors.py`.

A finding is `SUGGESTION` when style, naming, or organization could be improved but the code is correct.

## 11. Pointer to Language Mechanics

The rules above are the *principles*. The concrete mechanics — pytest configuration, ruff rules, mypy strictness, folder-detection logic — live in `.claude/rules/python.md`. The `/build` skill wires that file into `CLAUDE.md` before spawning the Dev subagent. If you are adding a new language ruleset, mirror the shape of `python.md` and keep the principle vocabulary consistent with this document.
