# ADII — Task A: Investigator & Agent Runtime

## What This Is

ADII is an Autonomous Data Incident Investigator that gathers evidence through a controlled
tool boundary and produces a structured operational decision. This planning context covers
only Task A: the investigator and agent runtime. Tasks B, C, and D remain separate work
tracks and appear here only where their interfaces constrain or block Task A.

## Core Value

The investigator must reach a defensible decision from controlled evidence without crossing
the tool, validation, or evaluation authority boundaries.

## Requirements

### Validated

- ✓ A deterministic scripted provider runs without network access, API keys, environment
  variables, or external model providers — Task A Phase 1
- ✓ The investigator loop emits ordered trace events and terminates only on explicit model
  STOP, while provider exhaustion remains a distinct failure — Task A Phase 2
- ✓ A validated model-turn budget enforces a hard pre-call ceiling and reports a distinct
  trace-carrying budget error — Task A Phase 3
- ✓ The loop constructs shared `ToolCall` values, invokes an injected executor, traces all
  `ToolResult` statuses uniformly, and hands each fresh result to the next provider call
  exactly once — Task A Phase 4
- ✓ Immutable investigation state accumulates exact `ToolResult` objects across turns, and
  deterministic tests prove that different evidence causes different next actions — Task A
  Phase 5

### Active

- [ ] Integrate the Task A loop with Task B's real controlled-tool executor without taking
  ownership of tool schemas, permissions, or implementations — Task A Phase 6
- [ ] Produce a structured shared-contract `InvestigationDecision` as the terminal Task A
  output — Task A Phase 7
- [ ] Populate valid REPAIR, NO_REPAIR, and ESCALATE decision content without allowing the
  investigator to validate or score itself — Task A Phase 8
- [ ] Handle provider, parsing, tool-result, and runtime failures with accurate attribution
  while preserving stopping and budget guarantees — Task A Phase 9
- [ ] Verify the complete Task A flow through Task-A-owned end-to-end integration tests using
  controlled external boundaries — Task A Phase 10

### Out of Scope

- Task B tool implementations, schemas, SQL, permissions, and environment access — owned by
  the controlled-tools work track
- Task C repair validation and acceptance — validation is an independent authority
- Task D evaluation, answer keys, scoring, persistence, reporting, and run archives — owned
  outside Task A
- Unilateral changes to `02_src/adii/contracts/core.py` — shared contracts require
  cross-boundary team review
- Direct filesystem, database, subprocess, or network access from the investigator — all
  observations must arrive through `02_src/adii/tools/`
- Rebuilding or redesigning approved Task A Phases 1–5 — they are completed historical work

## Context

- This is a brownfield repository with established architecture, contracts, tests, package
  responsibilities, and generated status documentation.
- The canonical repository guidance is `AGENTS.md`, `02_src/docs/system_map.md`,
  `02_src/docs/architecture.md`, `02_src/docs/build_plan.md`, and
  `02_src/docs/current_status.md`.
- The codebase map under `.planning/codebase/` records the implementation as of 2026-09-10.
- Task A currently provides a scripted provider, explicit-stop loop, turn budget, injected
  tool orchestration, ordered traces, one-shot observations, and accumulated immutable state.
- Phase 6 is an integration checkpoint. Its first planning duty is to identify Task B's real
  executor interface and any uncertainty without implementing Task B behavior inside Task A.
- The team develops on Windows and macOS with Python 3.12. CI also exercises Ubuntu.

## Constraints

- **Architecture**: The investigator sees the world only through the tool layer — bypassing
  it can expose hidden evaluation material and invalidates the system's evidence claim.
- **Authority**: Task A must never import validation or evaluation — proposal, validation,
  and scoring are separate programs and trust domains.
- **Contracts**: Use the eight shared types in `02_src/adii/contracts/core.py` unchanged —
  local convenience does not authorize cross-team contract edits.
- **Dependencies**: Production runtime code remains standard-library-only unless a dependency
  is explicitly reviewed and accepted.
- **Compatibility**: Preserve approved Phase 1–5 public behavior and existing tests while
  extending the runtime.
- **Delivery**: Anything important runs through `python -m ...`; do not add shell scripts,
  Docker, Redis, Postgres, or machine-specific infrastructure.
- **Evidence**: A claimed action must appear in the trace; provider and tool failures must be
  attributed to the correct boundary.
- **Scope**: This roadmap plans only Task A Phases 6–10. Tasks B, C, and D are dependencies,
  interfaces, or blockers, never implementation phases here.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Treat Task A Phases 1–5 as completed history | They are independently reviewed and approved; reopening them would recreate finished backlog | ✓ Good |
| Set Task A Phase 6 as the next active phase | Real-tool integration is the next dependency-bearing checkpoint | — Pending |
| Limit this GSD roadmap to Task A Phases 6–10 | Other tracks have different responsibilities and authorities | — Pending |
| Represent Tasks B/C/D only as external dependencies and boundaries | Prevents Task A from absorbing tool, validation, evaluation, or reporting ownership | — Pending |
| Preserve the investigator/tool/validation/evaluation boundaries | These boundaries are the core integrity property of ADII | ✓ Good |
| Keep shared contracts unchanged without cross-team review | Contract edits affect every work track and cannot be local refactors | ✓ Good |
| Plan before executing Phase 6 | Interface uncertainty must be surfaced before implementation crosses a team boundary | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone**:
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-09-10 after initialization*
