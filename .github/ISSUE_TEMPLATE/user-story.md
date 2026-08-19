---
name: User Story
about: Senior-grade story for the Smart Store harness. Use /story from Claude Code to auto-fill.
title: "[STORY] <verb-object> — <value>"
labels: ["user-story", "needs-refinement"]
assignees: ""
---

<!--
This template mirrors the format produced by the /story Claude Code skill.
If you are filling it by hand: every section must be complete. Empty sections
signal a lazy story and will be rejected by the Dev subagent.

Dependencies, Use Cases, and Test Matrix are BLOCKING sections — the Dev
subagent will refuse to start if any of them is empty or vague. See
.claude/skills/story/SKILL.md and .claude/agents/dev-agent.md for details.
-->

## Story

**As a** <Buyer | Ops | Admin>
**I want** <goal, imperative, one sentence>
**So that** <benefit grounded in a PRD §3 invariant when possible>

## Dependencies

**Data model:**
- `<table>` — <exists (alembic/versions/<file>.py) | new migration required: <verb> <what> | column added: <col> to <table>>

**Domain entities & value objects:**
- `<AggregateOrValueObject>` — <exists | new> — <file path under app/domain/>

**Application use cases:**
- `<UseCaseName>` — <exists | new> — <one-line behavior>

**Infrastructure:**
- Env vars: <e.g. DATABASE_URL, CORS_ORIGINS, or "none new">
- External services: <none in v1 unless the story explicitly requires one>
- Repository ports: <e.g. InventoryRepository (exists), ProductRepository (new)>

**Story blockers:**
- <#issue-number — one-line why, or "none">

## Use Cases

### `<UseCaseName>`
- **Behavior:** <one sentence>
- **Inputs:** <named fields + types>
- **Outputs:** <domain entity or event surfaced>
- **Failure modes:** <DomainError subclasses this use case may raise>

## Constraints

**Always:** <invariants that must hold, drawn from docs/PRD.md §3>
**Block If:** <conditions that must never be true on merge>
**Never:** <explicit exclusions>

## Acceptance Criteria

```gherkin
Scenario: <happy path>
  Given <precondition>
  When  <action>
  Then  <observable outcome>

Scenario: <edge case>
  Given <boundary precondition>
  When  <action>
  Then  <safe, defined outcome>

Scenario: <error handling>
  Given <invalid or unavailable dependency>
  When  <action>
  Then  <error surfaced with problem+json, no state corruption>
```

## Test Matrix

| Scenario | Layer(s) | Candidate test name |
|---|---|---|
| <happy path name> | unit / integration / e2e | `tests/<layer>/.../test_<verb>_<subject>.py::test_<behavior>` |
| <edge case name> | ... | ... |
| <error handling name> | ... | ... |

Rules the Dev subagent enforces from this matrix:
- Every row must have at least one layer.
- Concurrency, DB constraint, transaction, or `SELECT ... FOR UPDATE` in the Gherkin ⇒ `integration` is required.
- HTTP status code, response header, or wire format in the Gherkin ⇒ `e2e` is required.

## Definition of Done

- [ ] All AC scenarios pass in CI (unit + integration where the story implies concurrency, DB constraints, or transactions)
- [ ] Every row in the Test Matrix has at least one passing test at each named layer
- [ ] Every table under `Dependencies.Data model` exists at HEAD — either already present in `alembic/versions/`, or a new migration was added in this branch
- [ ] `uv run alembic upgrade head` completes cleanly on a fresh Postgres (verified by the integration testcontainer)
- [ ] `uv run alembic downgrade base && uv run alembic upgrade head` is reversible (or the migration file documents why not)
- [ ] `scripts/check_layers.sh` passes (no framework imports in `app/domain/`)
- [ ] No new ruff, ruff-format, or mypy violations
- [ ] PR body references this issue with `Closes #<n>`
- [ ] Alembic migration added if any schema change (with `CHECK` constraints where PRD §3 requires them)
- [ ] CHANGELOG entry under `[Unreleased]`
- [ ] Coverage remains at or above the floor in BEST_PRACTICES §4

## Out of Scope

- <items that keep this story small>

## Context

- Related PRD sections: <§ numbers>
- Related ARCHITECTURE sections: <e.g. §2 layer tree, §4 transaction boundary, §5 endpoint row>
- Related invariants (from PRD §3):
  - <invariant 1>
  - <invariant 2>
