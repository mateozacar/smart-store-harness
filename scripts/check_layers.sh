#!/usr/bin/env bash
# Enforces hexagonal layer isolation:
# - app/domain/ must not import framework modules or outer layers.
# - app/application/ must not import framework modules or outer layers.
set -euo pipefail

forbidden=$(grep -rnE '^(from|import) (fastapi|sqlalchemy|pydantic|httpx|app\.(infrastructure|interface))' app/domain/ || true)
if [ -n "$forbidden" ]; then
    echo "Layer violation in app/domain/:" >&2
    echo "$forbidden" >&2
    exit 1
fi

forbidden_app=$(grep -rnE '^(from|import) (fastapi|sqlalchemy|httpx|app\.(infrastructure|interface))' app/application/ || true)
if [ -n "$forbidden_app" ]; then
    echo "Layer violation in app/application/:" >&2
    echo "$forbidden_app" >&2
    exit 1
fi

echo "Layer check passed."
