#!/usr/bin/env bash
# UserPromptSubmit hook: when the user invokes /build or /story, record a
# baseline of cumulative token usage so the Stop hook can compute the delta
# attributable to that skill run.
#
# Input arrives on stdin as JSON: { session_id, transcript_path, cwd, prompt, ... }
# Output: writes .claude/state/tracking-active.json. Never blocks the prompt.

set -euo pipefail

INPUT=$(cat)
PROMPT=$(printf '%s' "$INPUT" | jq -r '.prompt // empty')
TRANSCRIPT_PATH=$(printf '%s' "$INPUT" | jq -r '.transcript_path // empty')

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(printf '%s' "$INPUT" | jq -r '.cwd // empty')}"
[ -n "$PROJECT_DIR" ] || exit 0

# Only track /build and /story invocations.
SKILL=""
ARGS=""
case "$PROMPT" in
  /build|/build\ *)
    SKILL="build"
    ARGS=$(printf '%s' "$PROMPT" | sed -E 's|^/build[[:space:]]*||')
    ;;
  /story|/story\ *)
    SKILL="story"
    ARGS=$(printf '%s' "$PROMPT" | sed -E 's|^/story[[:space:]]*||')
    ;;
  *)
    exit 0
    ;;
esac

STATE_DIR="$PROJECT_DIR/.claude/state"
mkdir -p "$STATE_DIR"

# Compute baseline cumulative usage from the transcript up to this point.
# Dedupe by message.id since the JSONL can contain repeated usage entries
# for the same API response.
BASELINE_JSON='{"input":0,"cache_read":0,"cache_creation":0,"output":0}'
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
  BASELINE_JSON=$(jq -s '
    [ .[] | select(.message.usage) | {id: .message.id, u: .message.usage} ]
    | unique_by(.id)
    | map(.u)
    | reduce .[] as $u ({input:0, cache_read:0, cache_creation:0, output:0};
        .input          += ($u.input_tokens                 // 0)
        | .cache_read     += ($u.cache_read_input_tokens      // 0)
        | .cache_creation += ($u.cache_creation_input_tokens  // 0)
        | .output         += ($u.output_tokens                // 0))
  ' "$TRANSCRIPT_PATH" 2>/dev/null || printf '%s' '{"input":0,"cache_read":0,"cache_creation":0,"output":0}')
fi

STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

jq -n \
  --arg skill      "$SKILL" \
  --arg args       "$ARGS" \
  --arg started_at "$STARTED_AT" \
  --arg transcript "$TRANSCRIPT_PATH" \
  --argjson baseline "$BASELINE_JSON" \
  '{skill:$skill, args:$args, started_at:$started_at, transcript:$transcript, baseline:$baseline}' \
  > "$STATE_DIR/tracking-active.json"

exit 0
