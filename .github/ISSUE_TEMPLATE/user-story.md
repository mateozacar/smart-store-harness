---
name: User Story
about: Senior-grade story for the Smart Store harness. Use /story from Claude Code to auto-fill.
title: "[STORY] <verb-object> — <value>"
labels: ["user-story", "needs-refinement"]
assignees: ""
---

<!--
This template mirrors the format produced by the /story Claude Code skill.
If you are filling it by hand: every section must be complete. Empty sections
signal a lazy story and will be rejected by the Dev subagent.
-->

## Story

**As a** <Buyer | Ops | Admin>
**I want** <goal, imperative, one sentence>
**So that** <benefit grounded in a PRD §3 invariant when possible>

## Constraints

**Always:** <invariants that must hold, drawn from docs/PRD.md §3>
**Block If:** <conditions that must never be true on merge>
**Never:** <explicit exclusions>

## Acceptance Criteria

```gherkin
Scenario: <happy path>
  Given <precondition>
  When  <action>
  Then  <observable outcome>

Scenario: <edge case>
  Given <boundary precondition>
  When  <action>
  Then  <safe, defined outcome>

Scenario: <error handling>
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

- <items that keep this story small>

## Context

- Related PRD sections: <§ numbers>
- Related invariants (from PRD §3):
  - <invariant 1>
  - <invariant 2>
