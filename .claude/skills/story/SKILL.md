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
- **Scenarios:** at least three Gherkin scenarios — one happy path, one edge / boundary, one error case. Concurrency scenarios are required if the story touches inventory, reservations, or any resource with a `reserved`/`available` invariant.

### 3. Render the issue body

Use exactly this structure. Every section must be filled; empty sections signal a lazy story and are rejected by the Dev subagent.

```markdown
## Story

**As a** <role>
**I want** <goal>
**So that** <benefit>

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

## Definition of Done

- [ ] All AC scenarios pass in CI (unit + integration where the story implies concurrency, DB constraints, or transactions)
- [ ] No new ruff, ruff-format, or mypy violations
- [ ] `scripts/check_layers.sh` passes (no framework imports in `app/domain/`)
- [ ] PR body references this issue with `Closes #<n>`
- [ ] Alembic migration added if any schema change (with `CHECK` constraints)
- [ ] CHANGELOG entry under `[Unreleased]`
- [ ] Coverage remains at or above the floor in BEST_PRACTICES §4

## Out of Scope

- <items that keep this story small; things a reader might reasonably expect but that belong to a separate story>

## Context

- Related PRD sections: <§ numbers, e.g., §3 /inventory, §4 Story 1>
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
- **No mixed concerns.** A story that touches two aggregates (e.g., orders + customers) is fine; a story that describes two independent behaviors is not.
- **No implementation details.** The story describes behavior, not code paths. Do not name classes, files, or SQL. Those decisions belong to the Dev subagent under the Architecture doc.
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
