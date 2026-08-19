#!/usr/bin/env bash
# scripts/bootstrap.sh
# Idempotent bootstrap for the Smart Store harness. Safe to re-run.
#
# Usage:
#   scripts/bootstrap.sh --owner <gh-user-or-org> --repo <repo-name> \
#                        [--project-name "Smart Store Harness"] [--public|--private]
#
# What it does (each step skipped if already satisfied):
#   A0. Write .gitignore
#   A1. git init on main + initial commit
#   A2. Create GitHub repo + push main
#   A3. Create develop branch + push
#   A4. Create GitHub Projects v2 board
#   A4.5. Configure Status field options: Ready | In Progress | In Review | Done
#   A5. Discover IDs and write .env.demo (delegates to scripts/discover-project-ids.sh)
#   A6. Write .mcp.json
#   A7. Verify toolchain (gh, uv, python)

set -euo pipefail

# ─── args ──────────────────────────────────────────────────────────────────
GITHUB_OWNER=""
GITHUB_REPO=""
PROJECT_NAME="Smart Store Harness"
VISIBILITY="--private"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner)         GITHUB_OWNER="$2"; shift 2 ;;
    --repo)          GITHUB_REPO="$2"; shift 2 ;;
    --project-name)  PROJECT_NAME="$2"; shift 2 ;;
    --public)        VISIBILITY="--public"; shift ;;
    --private)       VISIBILITY="--private"; shift ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -z "$GITHUB_OWNER" ]] && { echo "Missing --owner"  >&2; exit 1; }
[[ -z "$GITHUB_REPO"  ]] && { echo "Missing --repo"   >&2; exit 1; }

# ─── preflight ─────────────────────────────────────────────────────────────
command -v gh  >/dev/null 2>&1 || { echo "gh CLI not installed. https://cli.github.com" >&2; exit 1; }
command -v git >/dev/null 2>&1 || { echo "git not installed" >&2; exit 1; }
command -v jq  >/dev/null 2>&1 || { echo "jq not installed" >&2; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Not authenticated. Run: gh auth login --scopes repo,project,read:org" >&2; exit 1; }

log()  { printf '\033[32m✓\033[0m %s\n' "$*"; }
skip() { printf '\033[90m→\033[0m %s\n' "$*"; }

# ─── A0. .gitignore ────────────────────────────────────────────────────────
if [[ ! -f .gitignore ]]; then
  cat > .gitignore <<'GITIGNORE'
# secrets / env
.env
.env.*
!.env.example

# python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage
coverage.xml

# claude state (per-session, not source)
.claude/state/

# macOS
.DS_Store
GITIGNORE
  log "A0. .gitignore written"
else
  skip "A0. .gitignore already exists"
fi

# ─── A1. git init + initial commit ─────────────────────────────────────────
if [[ ! -d .git ]]; then
  git init -b main >/dev/null
  git add .
  git -c commit.gpgsign=false commit -m "chore: bootstrap harness with grounding docs and skills" >/dev/null
  log "A1. git initialized on main with initial commit"
else
  skip "A1. git already initialized"
fi

# ─── A2. Create GitHub repo + push ─────────────────────────────────────────
if ! git remote get-url origin >/dev/null 2>&1; then
  gh repo create "$GITHUB_OWNER/$GITHUB_REPO" "$VISIBILITY" --source=. --remote=origin --push >/dev/null
  log "A2. remote created and main pushed"
else
  skip "A2. remote 'origin' already configured"
  # If main is ahead of remote, push (best-effort; won't force)
  git push -u origin main 2>/dev/null || true
fi

# ─── A3. develop branch ────────────────────────────────────────────────────
if ! git ls-remote --exit-code --heads origin develop >/dev/null 2>&1; then
  current_branch=$(git branch --show-current)
  git checkout -B develop >/dev/null 2>&1
  git push -u origin develop >/dev/null
  git checkout "$current_branch" >/dev/null 2>&1
  log "A3. develop branch created and pushed"
else
  skip "A3. develop branch already on origin"
fi

# ─── A4. Projects v2 board ─────────────────────────────────────────────────
existing=$(gh project list --owner "$GITHUB_OWNER" --format json --limit 200 2>/dev/null \
  | jq -r --arg n "$PROJECT_NAME" '.projects[] | select(.title==$n) | .number' | head -1)

if [[ -z "$existing" ]]; then
  PROJECT_NUMBER=$(gh project create --owner "$GITHUB_OWNER" --title "$PROJECT_NAME" --format json \
    | jq -r '.number')
  log "A4. Projects v2 board '$PROJECT_NAME' created (number=$PROJECT_NUMBER)"
else
  PROJECT_NUMBER="$existing"
  skip "A4. Projects v2 board '$PROJECT_NAME' already exists (number=$PROJECT_NUMBER)"
fi

# ─── A4.5. Configure Status field options ──────────────────────────────────
PROJ_ID=$(gh api graphql -f query='
  query($login:String!, $number:Int!) {
    user(login:$login) { projectV2(number:$number) { id } }
    organization(login:$login) { projectV2(number:$number) { id } }
  }' -f login="$GITHUB_OWNER" -F number="$PROJECT_NUMBER" \
  --jq '.data.user.projectV2.id // .data.organization.projectV2.id')

if [[ -z "$PROJ_ID" || "$PROJ_ID" == "null" ]]; then
  echo "Could not resolve project node ID for #$PROJECT_NUMBER" >&2; exit 1
fi

STATUS_JSON=$(gh api graphql -f query='
  query($proj:ID!) {
    node(id:$proj) {
      ... on ProjectV2 {
        field(name:"Status") {
          ... on ProjectV2SingleSelectField { id options { id name } }
        }
      }
    }
  }' -f proj="$PROJ_ID")

STATUS_FIELD_ID=$(echo "$STATUS_JSON" | jq -r '.data.node.field.id')
CURRENT=$(echo "$STATUS_JSON" | jq -c '[.data.node.field.options[].name]')
DESIRED='["Ready","In Progress","In Review","Done"]'

if [[ "$CURRENT" != "$DESIRED" ]]; then
  gh api graphql -f query='
    mutation($field:ID!, $opts:[ProjectV2SingleSelectFieldOptionInput!]!) {
      updateProjectV2Field(input:{ fieldId:$field, singleSelectOptions:$opts }) {
        projectV2Field { ... on ProjectV2SingleSelectField { id options { id name } } }
      }
    }' \
    -f field="$STATUS_FIELD_ID" \
    -F opts='[
      {"name":"Ready","color":"GRAY","description":"Refined and ready for /build"},
      {"name":"In Progress","color":"YELLOW","description":"Dev subagent working"},
      {"name":"In Review","color":"BLUE","description":"PR open, awaiting review"},
      {"name":"Done","color":"GREEN","description":"Merged and closed"}
    ]' >/dev/null
  log "A4.5. Status options configured: Ready | In Progress | In Review | Done"
else
  skip "A4.5. Status options already correct"
fi

# ─── A5. Discover IDs → .env.demo ──────────────────────────────────────────
bash "$(dirname "$0")/discover-project-ids.sh" \
  --owner "$GITHUB_OWNER" \
  --repo "$GITHUB_REPO" \
  --project-number "$PROJECT_NUMBER"

# ─── A6. .mcp.json ─────────────────────────────────────────────────────────
if [[ ! -f .mcp.json ]]; then
  cat > .mcp.json <<MCP
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "\${GITHUB_PAT}" }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "$(pwd)"]
    }
  }
}
MCP
  log "A6. .mcp.json written"
else
  skip "A6. .mcp.json already exists"
fi

# ─── A7. Verify ────────────────────────────────────────────────────────────
echo ""
echo "─── Verification ───────────────────────────────────────────────────"
gh auth status 2>&1 | grep -E "Logged in|account" | head -2 || true
if command -v uv          >/dev/null 2>&1; then log "uv $(uv --version)"; else echo "✗ uv not installed. Install: https://docs.astral.sh/uv/"; fi
if command -v python3.12  >/dev/null 2>&1; then log "$(python3.12 --version)"; else echo "✗ Python 3.12 not on PATH (uv can manage it: uv python install 3.12)"; fi
if [[ -n "${GITHUB_PAT:-}" ]]; then log "GITHUB_PAT is set (MCP GitHub server will authenticate)"; else echo "! GITHUB_PAT not exported — set it before running /story if using the MCP server"; fi

echo ""
echo "─── Bootstrap complete ────────────────────────────────────────────"
echo "  Load env:      source .env.demo"
echo "  First story:   scripts/story-0.sh  (prints the exact /story command)"
echo "  Then in Claude Code:"
echo "     /story \"<the story text from scripts/story-0.sh>\""
echo "     /build <returned issue number>"
