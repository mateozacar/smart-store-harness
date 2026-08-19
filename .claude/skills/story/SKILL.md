---
name: story
description: "Create a GitHub user story issue with Connextra + Gherkin, add it to the Projects v2 board, and set its status to Ready. Invoke as /story \"<one-liner>\"."
allowed-tools:
  - Read
  - Bash
  - Write
  - mcp__github__create_issue
  - mcp__github__add_project_item
---

# /story — Create a User Story

Argument (`$ARGUMENTS`): a single-line description of the story in the user's own words. Example: `checkout as guest without creating an account`.

You are creating a work item that a Dev subagent will later consume verbatim. Every field you write becomes an instruction to that agent — sloppiness here produces sloppy code downstream. Ground every choice in `docs/PRD.md`.

## Prerequisites

Before doing anything else, verify all of the following. If any check fails, stop immediately and print exactly which one failed. Do not create partial state.

1. `$ARGUMENTS` is non-empty. If empty, print `Usage: /story "<one-liner describing the story>"` and exit.
2. `docs/PRD.md` exists at the repo root.
3. The following environment variables are set (loaded from `.env.demo` if using direnv, or from the shell): `GITHUB_OWNER`, `GITHUB_REPO`, `PROJECT_NUMBER`, `PROJ_ID`, `STATUS_FIELD_ID`, `READY_OPTION_ID`. Check with:
   ```bash
   : "${GITHUB_OWNER:?}"; : "${GITHUB_REPO:?}"; : "${PROJECT_NUMBER:?}"
   : "${PROJ_ID:?}"; : "${STATUS_FIELD_ID:?}"; : "${READY_OPTION_ID:?}"
   ```
4. `gh auth status` succeeds. If not, print `Not authenticated with gh. Run: gh auth login` and exit.

## Steps

### 1. Read the PRD

Read `docs/PRD.md`. From it, extract:
- The list of resources (§3) and their invariants — you will reference these in the Constraints and Context sections.
- The existing backlog (§4 for the initial story, §5 for the demo backlog).

If `$ARGUMENTS` clearly duplicates an item already in §4 or §5, stop and ask the user: *"This looks similar to <item>. Create a duplicate anyway, or cancel?"* Do not proceed without an explicit yes.

If `$ARGUMENTS` describes two behaviors joined by "and" or a comma (e.g., "list products and add discounts"), stop and ask the user to split it into two `/story` invocations. One story per branch.

### 2. Derive the story fields

From `$ARGUMENTS`, derive:

- **Title:** `[STORY] <verb-object> — <value>` (≤ 72 chars). Sentence case, no trailing period.
- **Role:** infer from context.
  - Customer-facing behavior → `Buyer`.
  - Inventory / order operations / seeding → `Ops`.
  - Internal-only admin → `Admin`.
- **Goal:** what the persona wants (imperative, one sentence).
- **Benefit:** why it matters, grounded in a PRD §3 invariant when possible.
- **Constraints:**
  - `Always:` — the invariants from PRD §3 that this story must preserve.
  - `Block If:` — the failure conditions that must never be true on merge.
  - `Never:` — explicit exclusions relevant to this story.
- **Dependencies (BLOCKING — see below):**
  - `Data model:` — for every PRD §3 resource the story touches, list the table(s) involved and their status. Statuses: `exists (see alembic/versions/<file>.py)`, `new migration required — adds <what>`, or `column added — <col> to <table>`. If the story is create-only for a resource whose table already exists in `alembic/versions/`, cite the exact migration file. Never write "TBD" or leave blank.
  - `Domain entities & value objects:` — list each aggregate/value object in `app/domain/` the story reads or mutates. Mark each as `exists` or `new`.
  - `Application use cases:` — list every use case class under `app/application/` this story adds or modifies (this is a preview of the "Use Cases" section below).
  - `Infrastructure:` — env vars needed (`DATABASE_URL`, `CORS_ORIGINS`, etc.), external services (none in v1), and any repository ports the story requires.
  - `Story blockers:` — GitHub issue numbers that must be merged before this story is buildable. `none` is a valid value only if you have verified it.
- **Use Cases:** enumerate every application-layer use case (a class under `app/application/`) the story introduces or modifies. Each entry: name + one-line behavior + inputs → outputs + failure modes it must surface. Even a "trivial" endpoint has one use case; do not skip.
- **Scenarios:** at least three Gherkin scenarios — one happy path, one edge / boundary, one error case. Concurrency scenarios are required if the story touches inventory, reservations, or any resource with a `reserved`/`available` invariant.
- **Test Matrix (BLOCKING):** for each Gherkin scenario, name the layer(s) it will be tested at (`unit`, `integration`, `e2e`) and one candidate test name. Rules:
  - Every pure-logic scenario ⇒ at least one `unit` test.
  - Every scenario that names concurrency, a DB constraint, a transaction boundary, or `SELECT ... FOR UPDATE` ⇒ at least one `integration` test (real Postgres via testcontainers).
  - Every scenario that names an HTTP status code, header, or wire format ⇒ at least one `e2e` test.

**Dependencies grounding rule.** Every entry under `Dependencies.Data model:` must be verifiable at the current commit: either the table exists in `alembic/versions/` and you cite the file, or the story adds a new migration and names the verb (`add_column`, `create_table`, `add_check_constraint`). If you cannot map a resource in the story to a concrete migration path, stop and ask the user to clarify the schema shape. Do not proceed with a placeholder.

### 3. Render the issue body

Use exactly this structure. Every section must be filled; empty sections signal a lazy story and are rejected by the Dev subagent.

```markdown
## Story

**As a** <role>
**I want** <goal>
**So that** <benefit>

## Dependencies

**Data model:**
- `<table>` — <exists (alembic/versions/<file>.py) | new migration required: <verb> <what> | column added: <col> to <table>>
- <one bullet per table this story reads or writes>

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

<one entry per application-layer use case this story introduces or modifies>

### `<UseCaseName>`
- **Behavior:** <one sentence>
- **Inputs:** <named fields + types, drawn from the PRD>
- **Outputs:** <domain entity returned or event surfaced>
- **Failure modes:** <DomainError subclass names — e.g. SkuConflict, InsufficientStock — one per line>

## Constraints

**Always:** <one-line invariant, or bulleted list if multiple>
**Block If:** <one-line condition, or bulleted list>
**Never:** <one-line exclusion, or bulleted list>

## Acceptance Criteria

```gherkin
Scenario: <happy path — short name>
  Given <precondition>
  When  <action>
  Then  <observable outcome>

Scenario: <edge case — short name>
  Given <boundary precondition>
  When  <action>
  Then  <safe, defined outcome>

Scenario: <error handling — short name>
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
- Any row that mentions concurrency, a DB constraint, a transaction, or `SELECT ... FOR UPDATE` in its Gherkin ⇒ `integration` is required.
- Any row that mentions an HTTP status code, response header, or wire format ⇒ `e2e` is required.

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

- <items that keep this story small; things a reader might reasonably expect but that belong to a separate story>

## Context

- Related PRD sections: <§ numbers, e.g., §3 /inventory, §4 Story 1>
- Related ARCHITECTURE sections: <e.g. §2 layer tree, §4 transaction boundary, §5 endpoint row>
- Related invariants (from PRD §3):
  - <invariant 1>
  - <invariant 2>
```

### 4. Create the GitHub issue

Call `mcp__github__create_issue` with:
- `owner`: `$GITHUB_OWNER`
- `repo`: `$GITHUB_REPO`
- `title`: the derived title from step 2
- `body`: the rendered markdown from step 3
- `labels`: `["user-story", "needs-refinement"]`

Capture the returned `number` (issue number), `html_url`, and `node_id` (the GraphQL node ID for the issue).

If this call fails, stop and print the exact error. Do not proceed to the Projects step.

### 5. Add the issue to the project board

Call `mcp__github__add_project_item` (or, if that MCP tool is unavailable, fall back to the shell command below) with:
- `project_id`: `$PROJ_ID`
- `content_id`: the `node_id` captured in step 4

```bash
# Fallback if the MCP tool is not available in this session
ITEM_ID=$(gh api graphql -f query='
  mutation($project:ID!,$content:ID!){
    addProjectV2ItemById(input:{projectId:$project, contentId:$content}){
      item { id }
    }
  }' -f project="$PROJ_ID" -f content="<node_id from step 4>" \
  --jq '.data.addProjectV2ItemById.item.id')
```

Capture the returned item `id` as `ITEM_ID`.

### 6. Set status to Ready

Run:

```bash
gh api graphql -f query='
  mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){
    updateProjectV2ItemFieldValue(input:{
      projectId:$project,
      itemId:$item,
      fieldId:$field,
      value:{singleSelectOptionId:$option}
    }){ projectV2Item { id } }
  }' \
  -f project="$PROJ_ID" \
  -f item="$ITEM_ID" \
  -f field="$STATUS_FIELD_ID" \
  -f option="$READY_OPTION_ID"
```

If this call fails but the issue and item were created, do not delete them. Print the `ITEM_ID` and a one-line fixup command the user can run to complete the transition manually.

### 7. Persist state for downstream tools

The Stop hook and the `/build` skill both need the issue number.

```bash
mkdir -p .claude/state
printf '%s\n' "<issue-number>" > .claude/state/last-issue.txt
```

### 8. Report

Print exactly this format (no extra prose):

```
Created issue #<n>: <title>
URL:   <html_url>
Board: status=Ready (item <ITEM_ID>)
Next:  /build <n>
```

## Behavioral rules

- **Ground every field in the PRD.** If a Constraint or invariant is not in `docs/PRD.md`, either you are wrong or the PRD is out of date. In the latter case, add this line to the Definition of Done: `- [ ] Propose PRD update: <describe the missing invariant>`. Do not silently invent invariants.
- **Dependencies is BLOCKING.** If the story touches any resource named in PRD §3 (`/products`, `/inventory`, `/orders`, `/customers`) and the rendered `## Dependencies` section leaves `Data model:` empty, or writes "TBD" / "N/A" / an unspecific value, stop before calling `mcp__github__create_issue`. Print `Dependencies incomplete: <what is missing>` and exit 1. The Dev subagent contract depends on this section being complete; a blank Dependencies is not a story, it is a wish.
- **Cite migrations by path.** When a table under `Dependencies.Data model` is marked `exists`, cite the exact file (`alembic/versions/<file>.py`). Do this by scanning `alembic/versions/` before rendering; do not guess. If no file creates the table you claim exists, either the table is genuinely new (adjust the entry to `new migration required`) or the story is grounded incorrectly (stop and re-read the PRD).
- **Use Cases must exist.** Every story produces at least one entry under `## Use Cases`. A story that seems to have "no use case" is either a refactor (which should not go through `/story`) or a UI-only change (out of scope for v1). Stop and ask.
- **Test Matrix must cover every scenario.** If any Gherkin scenario is missing a corresponding row in the Test Matrix, stop and complete the matrix before rendering. Concurrency/DB-constraint/transaction scenarios must have `integration` in their layers cell; HTTP-status/header/wire-format scenarios must have `e2e`.
- **No mixed concerns.** A story that touches two aggregates (e.g., orders + customers) is fine; a story that describes two independent behaviors is not.
- **No implementation details.** The story describes behavior, not code paths. Do not name classes, files, or SQL in `## Story` / `## Acceptance Criteria`. Naming *aggregates and use cases* in `## Dependencies` and `## Use Cases` is expected and correct — that is what makes those sections load-bearing for the Dev subagent.
- **No `bug` label from this skill.** Bugs use a separate `/bug` skill (not yet built). A `/story` invocation always produces a feature story.
- **Never edit or close existing issues.** This skill is create-only.
- **Never push to the repo or create branches.** That is `/build`'s job.

## Failure handling

| Failure point | Behavior |
|---|---|
| `$ARGUMENTS` empty | Print usage, exit 0. |
| Missing env var | Print which one, exit 1. |
| `gh auth status` fails | Print instruction, exit 1. |
| Duplicate story detected | Ask user before proceeding. |
| `Dependencies.Data model` empty or vague on a PRD §3 story | Print `Dependencies incomplete: <what>`, exit 1. No issue created. |
| Cited migration file does not exist under `alembic/versions/` | Print `Cited migration not found: <path>. Either the table is new or the story is wrong.`, exit 1. |
| Any Gherkin scenario missing from the Test Matrix | Print `Test Matrix incomplete: <scenario name>`, exit 1. |
| `mcp__github__create_issue` fails | Print error, exit 1. No Projects call. |
| `addProjectV2ItemById` fails | Issue exists but not on board. Print manual fixup query. Do not delete the issue. |
| Status mutation fails | Item exists on board with default status. Print manual fixup query. |
| `last-issue.txt` write fails | Warn but do not fail the overall run. |

## Rehearsal (dry-run)

For a talk rehearsal without hitting GitHub, invoke as `/story --dry-run "<one-liner>"`. When `--dry-run` is present in `$ARGUMENTS`:
- Perform steps 1–3 (read PRD, derive fields, render body).
- Print the full rendered body to stdout under a heading `--- dry-run: would create issue ---`.
- Skip steps 4–7 entirely.
- Print `Next: (dry-run; no issue created)`.
