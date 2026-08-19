#!/usr/bin/env bash
# Stop hook: if a /build or /story tracking marker is active, sum the token
# usage that accumulated in the transcript since the marker was written and
# append a TSV line to .claude/state/token-usage.log.
#
# Input arrives on stdin as JSON: { session_id, transcript_path, cwd, stop_hook_active, ... }
# Never blocks the stop; on any error, the marker is removed to avoid stale state.

set -euo pipefail

INPUT=$(cat)
TRANSCRIPT_PATH=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty')
STOP_HOOK_ACTIVE=$(printf '%s' "$INPUT" | jq -r '.stop_hook_active // false')

# Never recurse: if Claude re-entered because of a previous Stop hook, bail.
[ "$STOP_HOOK_ACTIVE" = "true" ] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(printf '%s' "$INPUT" | jq -r '.cwd // empty')}"
[ -n "$PROJECT_DIR" ] || exit 0

STATE_DIR="$PROJECT_DIR/.claude/state"
MARKER="$STATE_DIR/tracking-active.json"
LOG="$STATE_DIR/token-usage.log"

[ -f "$MARKER" ] || exit 0

# If we cannot compute a delta, remove the marker so it does not haunt future runs.
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
  rm -f "$MARKER"
  exit 0
fi

SKILL=$(jq -r '.skill'         "$MARKER")
ARGS=$(jq -r '.args'           "$MARKER")
STARTED_AT=$(jq -r '.started_at' "$MARKER")
B_IN=$(jq -r '.baseline.input'           "$MARKER")
B_CR=$(jq -r '.baseline.cache_read'      "$MARKER")
B_CC=$(jq -r '.baseline.cache_creation'  "$MARKER")
B_OUT=$(jq -r '.baseline.output'         "$MARKER")

CURRENT=$(jq -s '
  [ .[] | select(.message.usage) | {id: .message.id, u: .message.usage} ]
  | unique_by(.id)
  | map(.u)
  | reduce .[] as $u ({input:0, cache_read:0, cache_creation:0, output:0};
      .input          += ($u.input_tokens                 // 0)
      | .cache_read     += ($u.cache_read_input_tokens      // 0)
      | .cache_creation += ($u.cache_creation_input_tokens  // 0)
      | .output         += ($u.output_tokens                // 0))
' "$TRANSCRIPT_PATH")

C_IN=$(printf '%s' "$CURRENT" | jq -r '.input')
C_CR=$(printf '%s' "$CURRENT" | jq -r '.cache_read')
C_CC=$(printf '%s' "$CURRENT" | jq -r '.cache_creation')
C_OUT=$(printf '%s' "$CURRENT" | jq -r '.output')

D_IN=$((C_IN  - B_IN))
D_CR=$((C_CR  - B_CR))
D_CC=$((C_CC  - B_CC))
D_OUT=$((C_OUT - B_OUT))
TOTAL=$((D_IN + D_CR + D_CC + D_OUT))

# Resolve the issue number. For /build, prefer the first integer in the args
# (the user may have passed --dry-run alongside the number); otherwise fall
# back to .claude/state/last-issue.txt written by /story or a prior /build.
ISSUE=""
if [ "$SKILL" = "build" ]; then
  ISSUE=$(printf '%s' "$ARGS" | grep -oE '[0-9]+' | head -1 || true)
fi
if [ -z "$ISSUE" ] && [ -f "$STATE_DIR/last-issue.txt" ]; then
  ISSUE=$(tr -d '[:space:]' < "$STATE_DIR/last-issue.txt")
fi
[ -n "$ISSUE" ] || ISSUE="-"

FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Write TSV header once.
if [ ! -f "$LOG" ]; then
  printf 'timestamp_started\ttimestamp_finished\tskill\tissue\tinput\tcache_read\tcache_creation\toutput\ttotal\n' > "$LOG"
fi

printf '%s\t%s\t%s\t%s\t%d\t%d\t%d\t%d\t%d\n' \
  "$STARTED_AT" "$FINISHED_AT" "$SKILL" "$ISSUE" \
  "$D_IN" "$D_CR" "$D_CC" "$D_OUT" "$TOTAL" \
  >> "$LOG"

rm -f "$MARKER"
exit 0
