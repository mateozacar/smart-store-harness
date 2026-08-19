# Smart Store API

You are working on the Smart Store API, a small commerce backend used as the substrate for a near-autonomous Claude Code delivery harness. Before touching any code, load and respect the three grounding documents below. They are the source of truth for what to build, how to build it, and how well it must be built.

@docs/PRD.md
@docs/ARCHITECTURE.md
@docs/BEST_PRACTICES.md

Language-specific enforcement rules are loaded by the `/build` skill based on the detected primary language of this repository. When present, the following line is rewritten automatically before a Dev subagent is spawned.

@.claude/rules/python.md

## Non-negotiables
- Never modify PRD, ARCHITECTURE, or BEST_PRACTICES without an explicit user instruction. These are contracts, not scratchpads.
- Never introduce a framework import inside `app/domain/`.
- Tests must cover every Gherkin scenario plus happy-path and edge cases; they are written after implementation is complete, not interleaved with it.
- Never bypass the reservation transaction boundary described in ARCHITECTURE §4.
