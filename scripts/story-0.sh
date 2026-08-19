#!/usr/bin/env bash
# scripts/story-0.sh
# Prints the exact /story command for the initial project scaffold.
# Use it in rehearsal AND on stage — deterministic wording eliminates typos.
#
# Usage:
#   scripts/story-0.sh            # print the command
#   scripts/story-0.sh | pbcopy   # macOS: copy to clipboard
#   scripts/story-0.sh | wl-copy  # Wayland: copy to clipboard
#
# Then paste into the Claude Code prompt.

set -euo pipefail

STORY='Set up Python project scaffold with FastAPI, SQLAlchemy, Alembic, Docker Compose for local Postgres, and initial migrations for products, inventory, orders, customers'

# If stdout is a terminal, print help + command. If piped, print just the command.
if [ -t 1 ]; then
  cat <<INFO
─── Story 0 — Initial project scaffold ────────────────────────────────

Copy the /story command below and paste it into Claude Code:

  /story "$STORY"

What this story produces (via /build after /story):
  • pyproject.toml with the pinned toolchain from .claude/rules/python.md §1
  • app/ hexagonal skeleton per rules/python.md §10
  • Alembic initialized + first migration for products, inventory, orders, customers
  • docker-compose.yml for local Postgres 16
  • scripts/check_layers.sh (executable)
  • tests/e2e/test_healthz.py passing against docker-compose Postgres
  • CHANGELOG.md with [Unreleased] entry
  • Green pytest, ruff, ruff-format, mypy, layer-check

After /story, run:
  /build <returned issue number>

──────────────────────────────────────────────────────────────────────
INFO
else
  printf '/story "%s"\n' "$STORY"
fi
