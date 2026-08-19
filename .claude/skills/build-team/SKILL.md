---
name: build-team
description: "Like /build but delegates implementation to a multi-agent supervisor running in Herdr. Requires HERDR_ENV=1. Steps 1-7 and 9-15 are identical to /build; step 8 replaces the single dev-agent with the Herdr supervisor that fans out to domain agents in parallel. Invoke as /build-team <issue-number>."
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

# /build-team — Implement an Issue with a Multi-Agent Team

Argument (`$ARGUMENTS`): a GitHub issue number. If omitted, reads `.claude/state/last-issue.txt`.

This skill is identical to `/build` except step 8: instead of spawning a single `dev-agent`,
it starts the Herdr supervisor which fans out work to domain agents in parallel.

Requires `HERDR_ENV=1` — must be run from inside a Herdr-managed pane.

---

## Step 0 — Verify Herdr environment

```bash
test "${HERDR_ENV:-}" = 1 || { echo "Error: not inside Herdr. Open Herdr and run this from a managed pane."; exit 1; }
```

Also verify the supervisor agent is reachable:
```bash
herdr agent list | grep -q "supervisor" || echo "(supervisor not yet running — will be started)"
```

---

## Steps 1–7 — Identical to /build

Run exactly the same steps 1–7 from the `/build` skill:

1. Resolve the issue number from `$ARGUMENTS` or `.claude/state/last-issue.txt`
2. Fetch the issue via `mcp__github__get_issue` (validate it is open)
3. Compute branch name: `feature/<n>-<slug>`
4. Find the Projects v2 item ID
5. Transition board status → **In Progress**
6. Create and check out the feature branch from `develop`
7. Load language ruleset (rewrite `@.claude/rules/*.md` line in CLAUDE.md)

---

## Step 8 — Delegate to the Herdr Supervisor

This is the only step that differs from `/build`.

### 8a. Check for a running supervisor agent

```bash
herdr agent list --json
```

If no agent named `supervisor` is running, split a new pane and start one:

```bash
herdr pane split --current --direction right --cwd "$PWD" --no-focus
# use returned .result.pane.pane_id:
herdr agent start supervisor --kind claude-code --pane <pane_id>
```

### 8b. Send the supervisor its task

Compose the prompt from `scripts/prompts/supervisor.md` with the issue number injected:

```bash
SUPERVISOR_PROMPT="$(cat scripts/prompts/supervisor.md)

---
## Active issue
Issue number: $ISSUE_NUMBER
Branch already created: $BRANCH (checked out, based on develop)
Board status: already set to In Progress — do NOT transition it again.
After opening the PR, skip board transitions — /build-team handles them in step 14.
"

herdr agent prompt supervisor "$SUPERVISOR_PROMPT" --wait --timeout 1800000
```

`--wait` blocks until the supervisor finishes (idle/done). Timeout is 30 minutes.

### 8c. Read the supervisor's result

```bash
herdr agent read supervisor --source recent-unwrapped --lines 120
```

Parse the output for the integration branch name (`feat/issue-<n>-integration`) and PR URL.
If the supervisor reports a failure or blocked state, stop here — do not proceed to quality gates.

---

## Steps 9–15 — Identical to /build

Continue with the same steps 9–15 from the `/build` skill:

9. Read and validate the report (check for failure markers)
10. Verify quality gates on the integration branch:
    ```bash
    uv run ruff check app tests
    uv run ruff format --check app tests
    uv run mypy app
    uv run pytest -q --cov=app --cov-report=term-missing --cov-fail-under=85
    bash scripts/check_layers.sh
    ```
11. Confirm all work is committed and the integration branch has commits beyond `develop`
12. Push the integration branch (the supervisor may have already done this — check before pushing)
13. Open PR against `develop` if not already opened by the supervisor
14. Transition board status → **In Review**
15. Persist `.claude/state/last-pr.txt` and print the final report

---

## Final report format

```
Issue:    #<n> — <title>
Branch:   feat/issue-<n>-integration  (pushed to origin)
PR:       <pr_url>
Status:   Ready → In Progress → In Review
Agents:   <comma-separated list of domain agents that did work>
Skipped:  <comma-separated list of domain agents that returned NO_WORK_NEEDED>
Tests:    <count> passed  (coverage <pct>%)
Gates:    ruff ✓  ruff-format ✓  mypy ✓  layers ✓  pytest ✓
Next:     Await Claude Code Review action; merge to develop when green.
```

---

## Behavioral rules

- Same rules as `/build` plus:
- Never write feature code inside this skill — all code comes from domain agents.
- If `HERDR_ENV=1` is not set, stop immediately and tell the user to open Herdr first.
- If the supervisor opens a PR, do not open a second one — check `gh pr list --head feat/issue-<n>-integration` before step 13.
- The integration branch (`feat/issue-<n>-integration`) is the one that gets the PR, not the individual domain branches.
