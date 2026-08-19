# Task: Review Agent

You are the review agent. Your job is to review the completed worker branches and open pull requests.
You do not write code. You review, report, and open PRs.

---

## Step 1 — Identify completed branches

Run:
```bash
git branch -a | grep feat/
```

You should see:
- `feat/inventory-router`
- `feat/products-get-by-sku`
- `feat/orders-get-patch`

---

## Step 2 — Review each branch

For each branch, check out its worktree and review the diff against `develop`:

```bash
git diff develop...feat/<branch-name> --stat
git diff develop...feat/<branch-name>
```

For each branch, verify:

**Architecture compliance:**
- No imports of `fastapi`, `sqlalchemy`, `pydantic`, or `httpx` inside `app/domain/`
- No imports of `fastapi`, `sqlalchemy`, or `httpx` inside `app/application/`
- Run the layer check: `bash scripts/check_layers.sh`

**Tests:**
- Every new endpoint has at least a unit test and an e2e test
- Test names describe behavior (e.g. `test_returns_404_when_sku_not_found`)

**API correctness:**
- 404 responses use problem+json format
- 409 responses use problem+json format
- New routes include `responses=` dict documenting error shapes

**Code quality:**
- Functions ≤ 40 lines
- No dead code or TODO comments
- No broad `except Exception:`

---

## Step 3 — Run the full test suite from each worktree

For each worktree, navigate to it and run:
```bash
uv run pytest -x -q
uv run ruff check app tests
uv run mypy app
```

Report any failures.

---

## Step 4 — Open pull requests

For each branch that passes review, open a PR against `develop`:

```bash
gh pr create \
  --base develop \
  --head feat/<branch-name> \
  --title "<title>" \
  --body "<body>"
```

PR body must include:
- Summary of what was implemented (bullet points)
- Test coverage note
- `Closes #<issue-number>` if applicable

---

## Step 5 — Report

Print a final summary:

```
REVIEW COMPLETE

feat/inventory-router     → PASS  → PR #XX opened
feat/products-get-by-sku  → PASS  → PR #XX opened
feat/orders-get-patch     → PASS  → PR #XX opened

Issues found: none / <list any blocking issues>
```

If any branch has a BLOCKING issue (layer violation, failing tests, missing error mapping),
report it and do NOT open a PR for that branch. Instead describe exactly what needs to be fixed.
