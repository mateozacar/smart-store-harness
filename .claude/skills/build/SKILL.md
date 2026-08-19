---
name: build
description: "Consume a GitHub user-story issue, create a Gitflow feature branch, run the TDD Dev subagent, verify quality gates, open a PR against develop, and transition the Projects v2 status Ready → In Progress → In Review. Invoke as /build <issue-number> (or /build with no arg to reuse the last /story issue)."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Agent
  - mcp__github__get_issue
  - mcp__github__create_branch
  - mcp__github__push_files
  - mcp__github__create_pull_request
---

# /build — Implement an Issue End-to-End

Argument (`$ARGUMENTS`): an integer GitHub issue number. If omitted, the skill reads `.claude/state/last-issue.txt` (written by the last `/story` invocation). If neither is available, the skill stops.

You are the deterministic scaffolding around one story. The creative work — writing tests and code — is delegated to the `dev-agent` subagent in step 8. Your job is to *prepare, transition, verify, hand off, and finalize*. Do not write feature code yourself; that violates the separation of concerns and blows the demo timing.

## Prerequisites

Stop and report immediately if any check fails.

1. Issue number resolvable: `$ARGUMENTS` is a positive integer, or `.claude/state/last-issue.txt` exists with one.
2. Env vars set:
   - `GITHUB_OWNER`, `GITHUB_REPO`
   - `PROJ_ID`, `STATUS_FIELD_ID`
   - `IN_PROGRESS_OPTION_ID`, `IN_REVIEW_OPTION_ID`
3. `gh auth status` succeeds.
4. `git config user.email` and `git config user.name` are set (needed for branch commits).
5. Working tree is clean on the current branch. If `git status --porcelain` is non-empty, stop and ask the user to commit or stash.
6. `origin/develop` exists. If not, stop and print: `Create develop from main: git checkout -b develop main && git push -u origin develop`.

## Steps

### 0. Build plan — show execution progress upfront

Before taking any action, create a task list that mirrors every step of this skill. This gives the user a live progress view for the entire build run.

Call `TaskCreate` for each of the following tasks **in a single burst** (all pending, no dependencies yet):

| # | Subject | activeForm |
|---|---|---|
| 1 | Resolve issue number | Resolving issue |
| 2 | Fetch issue from GitHub | Fetching issue |
| 3 | Compute Gitflow branch name | Computing branch name |
| 4 | Find Projects v2 item ID | Looking up board item |
| 5 | Transition status → In Progress | Transitioning status |
| 6 | Create and check out feature branch | Creating branch |
| 7 | Load language ruleset | Loading ruleset |
| 8 | Spawn dev-agent subagent | Running dev-agent |
| 9 | Read and validate subagent report | Reading report |
| 10 | Verify quality gates | Running quality gates |
| 11 | Confirm all work is committed | Checking commits |
| 12 | Push branch to origin | Pushing branch |
| 13 | Open PR against develop | Opening PR |
| 14 | Transition status → In Review | Transitioning status |
| 15 | Persist state and report | Finalizing |

As each step begins, mark its task `in_progress`. When it completes successfully, mark it `completed`. If a step fails and the skill must stop, mark that task `in_progress` (blocked) and leave remaining tasks `pending`.

Then proceed immediately — no user confirmation needed.

### 1. Resolve the issue number

```bash
if [ -n "$ARGUMENTS" ] && [ "$ARGUMENTS" != "--dry-run" ]; then
  ISSUE_NUMBER=$(echo "$ARGUMENTS" | awk '{print $1}')
elif [ -f .claude/state/last-issue.txt ]; then
  ISSUE_NUMBER=$(cat .claude/state/last-issue.txt)
else
  echo "No issue number provided and no .claude/state/last-issue.txt." >&2; exit 1
fi
```

If `--dry-run` is present anywhere in `$ARGUMENTS`, set `DRY_RUN=1`.

### 2. Fetch the issue

Call `mcp__github__get_issue` with `owner=$GITHUB_OWNER`, `repo=$GITHUB_REPO`, `issue_number=$ISSUE_NUMBER`. Capture: `title`, `body`, `state`, `labels`, `node_id`.

Validate:
- `state == "open"`. If closed, stop.
- Body contains all of `## Story`, `## Constraints`, `## Acceptance Criteria`, `## Definition of Done`. If any is missing, print a warning (`Non-standard issue body; dev-agent may struggle`) and continue.

### 3. Compute branch name (Gitflow)

```bash
SLUG=$(printf '%s' "$TITLE" \
  | sed -E 's/^\[STORY\][[:space:]]*//' \
  | tr '[:upper:]' '[:lower:]' \
  | sed -E 's/[^a-z0-9]+/-/g' \
  | sed -E 's/^-+|-+$//g' \
  | cut -c1-40 \
  | sed -E 's/-+$//')
BRANCH="feature/${ISSUE_NUMBER}-${SLUG}"
```

Example: title `[STORY] Add inventory reservation when creating an order — atomicity` → branch `feature/1-add-inventory-reservation-when-creatin`.

### 4. Find the Projects v2 item ID for this issue

The status mutations need the *item* ID, not the issue node ID.

```bash
ITEM_ID=$(gh api graphql -f query='
  query($project:ID!){
    node(id:$project){
      ... on ProjectV2 {
        items(first:100){ nodes { id content { ... on Issue { id number } } } }
      }
    }
  }' -f project="$PROJ_ID" \
  --jq --arg n "$ISSUE_NUMBER" '.data.node.items.nodes[] | select(.content.number == ($n|tonumber)) | .id')

if [ -z "$ITEM_ID" ]; then
  echo "Issue #$ISSUE_NUMBER is not on the project board (PROJ_ID=$PROJ_ID)." >&2
  echo "Run /story again or add it manually with: gh api graphql ... addProjectV2ItemById" >&2
  exit 1
fi
```

For projects with > 100 items, extend with pagination via `pageInfo`.

### 5. Transition status → In Progress

```bash
gh api graphql -f query='
  mutation($project:ID!,$item:ID!,$field:ID!,$option:String!){
    updateProjectV2ItemFieldValue(input:{
      projectId:$project, itemId:$item, fieldId:$field,
      value:{singleSelectOptionId:$option}
    }){ projectV2Item { id } }
  }' \
  -f project="$PROJ_ID" -f item="$ITEM_ID" \
  -f field="$STATUS_FIELD_ID" -f option="$IN_PROGRESS_OPTION_ID"
```

Skip if `DRY_RUN=1`.

### 6. Create the branch and check it out

Call `mcp__github__create_branch` with `owner=$GITHUB_OWNER`, `repo=$GITHUB_REPO`, `branch=$BRANCH`, `from_branch=develop` to create the remote branch. Then check it out locally:

```bash
git fetch origin
git checkout -b "$BRANCH" "origin/$BRANCH"
```

If `mcp__github__create_branch` fails, fall back to:

```bash
git fetch origin develop
gh issue develop "$ISSUE_NUMBER" --name "$BRANCH" --base develop --checkout
```

The `Closes #<n>` in the PR body is what auto-closes the issue on merge; no special branch-issue link is required.

Skip if `DRY_RUN=1`.

### 7. Load the language ruleset

```bash
if   [ -f pyproject.toml ]; then LANG=python
elif [ -f package.json ];   then LANG=typescript
elif [ -f go.mod ];         then LANG=go
else
  echo "Cannot detect language. Missing pyproject.toml / package.json / go.mod." >&2; exit 1
fi

if [ ! -f ".claude/rules/${LANG}.md" ]; then
  echo "Missing .claude/rules/${LANG}.md. Author it before running /build." >&2; exit 1
fi

# Rewrite the @-include line in CLAUDE.md
if grep -qE '^@\.claude/rules/[a-z]+\.md' CLAUDE.md; then
  # Portable sed (works on macOS BSD sed and GNU sed)
  perl -i -pe "s|^\@\.claude/rules/[a-z]+\.md|\@.claude/rules/${LANG}.md|" CLAUDE.md
else
  printf '\n@.claude/rules/%s.md\n' "$LANG" >> CLAUDE.md
fi
```

The rewrite must land in the same commit as the story work, not in a separate cleanup commit — the dev-agent handles this.

### 8. Spawn the Dev subagent

Invoke the `dev-agent` subagent (definition: `.claude/agents/dev-agent.md`) via the Agent tool with:

- `subagent_type: "dev-agent"`
- `isolation: "worktree"` — the subagent works in an isolated git worktree so parallel `/build` invocations do not collide.
- Prompt containing:
  1. The full issue body (verbatim).
  2. The branch name.
  3. The detected language.
  4. A one-line reminder that CLAUDE.md loads all grounding docs and that mechanics live in `.claude/rules/${LANG}.md`.

Wait for the subagent to complete. Capture the final report exactly as printed.

Skip this step if `DRY_RUN=1`; instead print `Would spawn dev-agent with issue #<n> on branch <branch> in language <lang>`.

### 9. Read the subagent report

Parse the report format defined in `.claude/agents/dev-agent.md` ("Report format"). If it starts with `Dev subagent FAILED`:

- Do NOT push.
- Do NOT open a PR.
- Do NOT transition status.
- Print the failure block and exit 1. Leave the branch as the subagent left it; a human takes over.

### 10. Verify quality gates (defense in depth)

Even if the subagent claims success, re-run every gate from the checked-out worktree:

```bash
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under=85
bash scripts/check_layers.sh
```

Any non-zero exit → stop before push. Print which gate failed and its output. Status remains In Progress; branch is retained locally.

**Migration verification.** Parse the `## Dependencies` → `Data model:` section from the issue body. For every table listed, grep `alembic/versions/` for a `create_table("<name>"` or `add_column("<name>"` reference. Missing ⇒ stop before push and print `Migration missing for table: <name>`. This is the gate that would have caught the Render #6 incident where `products` compiled and deployed without a migration referenced.

### 11. Confirm all work is committed

```bash
if [ -n "$(git status --porcelain)" ]; then
  echo "Dev subagent left uncommitted changes:" >&2
  git status
  exit 1
fi
if [ -z "$(git log develop..HEAD --oneline)" ]; then
  echo "No commits on $BRANCH beyond develop. Nothing to PR." >&2
  exit 1
fi
```

### 12. Push the branch

Collect all files changed on the branch relative to `develop`, read their contents, and push via MCP:

1. `git diff origin/develop..HEAD --name-only` — list changed paths.
2. For each path, read its current content.
3. Call `mcp__github__push_files` with `owner=$GITHUB_OWNER`, `repo=$GITHUB_REPO`, `branch=$BRANCH`, `files=[{path, content}]`, `message="feat: implement story #$ISSUE_NUMBER"`.

If `mcp__github__push_files` fails (e.g. binary files, oversized diff, auth), fall back to:

```bash
git push -u origin "$BRANCH"
```

If both fail, print the exact error and the manual command. Do not transition status further.

### 13. Open the PR against `develop`

Compose the PR body:

```
Closes #<ISSUE_NUMBER>

## Summary
<one-paragraph derived from the issue's "## Story" section>

## Test plan
- [ ] <one bullet per Gherkin scenario in the issue's "## Acceptance Criteria" section>

## Grounding docs consulted
- docs/PRD.md (invariants + backlog)
- docs/ARCHITECTURE.md (layers, transaction boundary)
- docs/BEST_PRACTICES.md (quality bar)
- .claude/rules/<LANG>.md (mechanics)

## Dev subagent report
<paste the full report block printed by dev-agent>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

Call `mcp__github__create_pull_request` (or fall back to `gh pr create`) with:
- `base: develop`
- `head: $BRANCH`
- `title: feat: <derived from issue title, [STORY] prefix stripped>`
- `body: <rendered above>`
- `draft: false`

Capture the PR `number` and `html_url`.

### 14. Transition status → In Review

Same GraphQL mutation as step 5, with `option="$IN_REVIEW_OPTION_ID"`.

If this fails, the PR still exists. Print the item ID and the manual mutation.

### 15. Persist state

```bash
printf '%s\n' "$PR_NUMBER" > .claude/state/last-pr.txt
```

The Done transition on merge is handled by `.github/workflows/close-on-merge.yml` (not by this skill; that workflow runs on `pull_request.closed` with `merged == true`).

### 16. Report

Print exactly this block (no extra prose):

```
Issue:    #<n> — <title>
Branch:   <branch>  (pushed to origin)
PR:       <pr_url>
Status:   Ready → In Progress → In Review
Tests:    <count> passed  (coverage <pct>%)
Gates:    ruff ✓  ruff-format ✓  mypy ✓  layers ✓  pytest ✓  migrations ✓
Subagent: <one-line summary from dev-agent's Notes field>
Next:     Await Claude Code Review action; merge to develop when green.
```

## Behavioral rules

- **Never write feature code inside this skill.** Scaffolding, git operations, MCP calls, GraphQL mutations only. All source edits happen inside the `dev-agent` subagent.
- **Never push without passing quality gates.** Step 10 is defense in depth; even if the subagent lied, this skill will not.
- **Never advance status past what actually happened.** If the PR failed to open, do not transition to In Review.
- **Never rewrite history on the branch after push.** Use additive commits only. No `--force`, no `--amend`.
- **Never bypass `gh issue develop`.** It is the only path that registers the branch↔issue link.
- **Never open a PR on `main`.** Only on `develop`. Prod deploys travel `develop → main` via a separate PR gated by the `production` environment (that PR is not created by this skill).
- **Never modify grounding docs.** `docs/PRD.md`, `docs/ARCHITECTURE.md`, `docs/BEST_PRACTICES.md`, and `.claude/rules/*.md` are read-only during a build.

## Failure handling

| Point of failure | Behavior | Status left at |
|---|---|---|
| Missing arg + no state file | Print usage, exit 1. | (unchanged) |
| Missing env var | Print which, exit 1. | (unchanged) |
| Issue closed | Stop, exit 0. | (unchanged) |
| Working tree dirty | Stop, ask user to commit/stash. | (unchanged) |
| Issue not on board | Stop, print fixup command. | (unchanged) |
| Language file missing | Stop, ask user to author `.claude/rules/<lang>.md`. | (unchanged) |
| Branch already exists locally | Check out existing; if it points elsewhere, stop. | (unchanged) |
| Branch already exists on origin | Stop; ask user (may indicate a stale prior run). | (unchanged) |
| Dev subagent FAILED report | Stop before push. Human triages. | In Progress |
| Any quality gate fails | Stop before push. Print gate output. | In Progress |
| MCP branch create fails | Fall back to `gh issue develop`. | (unchanged) |
| MCP push fails | Fall back to `git push -u origin "$BRANCH"`. | In Progress |
| Both push paths fail | Print manual command. | In Progress |
| PR creation fails | Print manual `gh pr create`. Branch is on origin. | In Progress |
| In Review mutation fails | Print manual mutation. PR is open. | In Progress (fix by hand) |

## Rehearsal (dry-run)

`--dry-run` in `$ARGUMENTS`:
- Perform steps 1–4 and 7 (detection + item lookup).
- Print each subsequent step as `WOULD: <describe action>`.
- Do not transition status, do not create branch, do not spawn subagent, do not push, do not open PR.
- Final line: `Next: (dry-run; nothing was created or transitioned)`.
