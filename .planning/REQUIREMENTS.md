# Requirements: ADII — Task A Remaining Runtime

**Defined:** 2026-09-10
**Core Value:** The investigator must reach a defensible decision from controlled evidence
without crossing the tool, validation, or evaluation authority boundaries.

## Completed Historical Baseline

These capabilities are validated by approved Task A Phases 1–5. They are context for the
remaining work, not implementation backlog and not phases to recreate.

- ✓ **HIST-01**: Deterministic scripted provider with explicit exhaustion behavior — Phase 1
- ✓ **HIST-02**: Explicit-stop investigator loop with ordered trace events — Phase 2
- ✓ **HIST-03**: Strict model-turn budget with distinct budget failure — Phase 3
- ✓ **HIST-04**: Injected `ToolCall` → executor → `ToolResult` orchestration with one-shot
  observation handoff — Phase 4
- ✓ **HIST-05**: Immutable accumulated investigation state and causally state-dependent next
  actions — Phase 5

## v1 Requirements

Only these remaining Task A requirements belong in the roadmap.

### Task B Integration

- [ ] **INTG-01**: Phase 6 begins by determining whether Task B's real controlled-tool
  executor exists and documenting its concrete callable interface, stability, and remaining
  dependencies before Task A implementation begins.
- [ ] **INTG-02**: Phase 6 is explicitly marked blocked when Task B's executor or required
  interface cannot be confirmed, without substituting fake production behavior or inventing
  an interface.
- [ ] **INTG-03**: Once confirmed, the Task A loop invokes Task B's real controlled-tool
  boundary using the existing shared `ToolCall` and `ToolResult` contracts without taking
  ownership of tool schemas, permissions, SQL, or environment access.
- [ ] **INTG-04**: Real-boundary integration preserves all four `ToolResult` statuses as
  observations, exact result handoff, accumulated state, logical turn accounting, and
  contiguous tracing.

### Structured Decision

- [ ] **DECI-01**: A normally completed investigation produces a shared-contract
  `InvestigationDecision` rather than ending with trace-only or free-text output.
- [ ] **DECI-02**: The terminal decision satisfies the existing construction invariants in
  `02_src/adii/contracts/core.py` without modifying or shadowing that contract.
- [ ] **DECI-03**: Decision production consumes Task A's accumulated investigation knowledge
  while remaining separate from repair validation, acceptance, evaluation, and scoring.

### Disposition Content

- [ ] **DISP-01**: A REPAIR decision carries a non-empty root-cause explanation, repair ID,
  and bounded patch content accepted by the existing `InvestigationDecision` contract.
- [ ] **DISP-02**: A NO_REPAIR decision explains why the observed condition is legitimate and
  carries neither a repair ID nor patch content.
- [ ] **DISP-03**: An ESCALATE decision identifies the missing evidence or authority that
  prevents a justified call and carries neither a repair ID nor patch content.
- [ ] **DISP-04**: Deterministic Task A tests can reach all three dispositions without
  consulting validation or evaluation.

### Reliability

- [ ] **RELI-01**: Malformed model output is attributed to the model/output boundary and does
  not escape as an unclassified platform failure.
- [ ] **RELI-02**: Provider failure, provider script exhaustion, explicit STOP, and turn-budget
  exhaustion remain structurally distinct outcomes.
- [ ] **RELI-03**: `DENIED`, `REJECTED`, and `ERROR` tool results retain their distinct meanings
  and remain normal investigator observations rather than loop crashes.
- [ ] **RELI-04**: Turn-budget and explicit-stopping guarantees remain enforced across malformed
  output, provider failure, and tool-result failure paths.
- [ ] **RELI-05**: Reliability behavior remains deterministic and leaves an accurate,
  contiguous trace sufficient to identify the boundary where failure occurred.

### Task A End-to-End Verification

- [ ] **E2E-01**: Task-A-owned integration tests drive an `IncidentContext` through the
  deterministic provider, confirmed Task B tool boundary, accumulated investigation state,
  and structured terminal decision.
- [ ] **E2E-02**: End-to-end tests cover successful disposition production and the distinct
  provider-exhaustion, budget-exhaustion, malformed-output, and tool-status paths owned by
  Task A.
- [ ] **E2E-03**: End-to-end verification proves the investigator performs no direct
  filesystem, database, subprocess, or network access and never imports validation or
  evaluation.
- [ ] **E2E-04**: Task A's final verification passes focused tests, architecture tests, the
  full repository suite, Ruff, and generated-status synchronization without weakening
  existing Phase 1–5 assertions.
- [ ] **E2E-05**: Task-A-only integration tests stop at the decision boundary and do not claim
  repair acceptance, evaluation correctness, scoring, persistence, or reporting behavior.

## v2 Requirements

Deferred to a separate follow-up milestone after the deterministic Task A runtime is complete
and approved.

### External Model Provider

- **PROV-01**: Add a real external model provider through the existing duck-typed provider
  boundary without redesigning the investigation loop.
- **PROV-02**: Introduce provider credentials, network configuration, and provider-specific
  dependencies only through a separately approved design and security review.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Task B tool implementations, schemas, permissions, SQL, and environment access | Owned by Task B; Task A integrates only through the confirmed boundary |
| Task C repair validation and acceptance | Validation is an independent authority |
| Task D evaluation, answer keys, scoring, persistence, and reporting | Owned by separate work tracks and outside this roadmap |
| Unilateral shared-contract changes | `02_src/adii/contracts/core.py` requires cross-team review |
| Real OpenAI, Anthropic, or other network provider integration | Explicitly deferred beyond Task A Phases 6–10 |
| API keys, provider environment variables, or provider SDK dependencies | Not required by the deterministic runtime roadmap |
| Reimplementation of Task A Phases 1–5 | Completed, reviewed, and approved historical work |
| Automatic phase execution or progression | Every plan and completed implementation requires explicit human approval |

## Acceptance Criteria

- Every v1 requirement maps to exactly one of Task A Phases 6–10.
- Phases 1–5 remain recorded as completed history and are not added to pending roadmap work.
- Phase 6 begins with interface discovery and remains blocked until the Task B boundary is
  confirmed.
- No phase implements Task B, C, or D responsibilities or changes shared contracts without
  explicit cross-team approval.
- Each implementation plan is bounded, independently reviewable, and followed by automated
  checks plus explicit human approval before progression.

## Definition of Done

Task A Phases 6–10 are complete only when every v1 requirement is implemented, verified,
reviewed, and explicitly approved; all repository test and lint gates pass; cross-team
boundaries remain intact; and no unresolved dependency is represented as completed work.

## Traceability

Populated during roadmap creation. Historical `HIST-*` items are intentionally excluded from
pending phase coverage.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INTG-01 | Phase 6 | Pending |
| INTG-02 | Phase 6 | Pending |
| INTG-03 | Phase 6 | Pending |
| INTG-04 | Phase 6 | Pending |
| DECI-01 | Phase 7 | Pending |
| DECI-02 | Phase 7 | Pending |
| DECI-03 | Phase 7 | Pending |
| DISP-01 | Phase 8 | Pending |
| DISP-02 | Phase 8 | Pending |
| DISP-03 | Phase 8 | Pending |
| DISP-04 | Phase 8 | Pending |
| RELI-01 | Phase 9 | Pending |
| RELI-02 | Phase 9 | Pending |
| RELI-03 | Phase 9 | Pending |
| RELI-04 | Phase 9 | Pending |
| RELI-05 | Phase 9 | Pending |
| E2E-01 | Phase 10 | Pending |
| E2E-02 | Phase 10 | Pending |
| E2E-03 | Phase 10 | Pending |
| E2E-04 | Phase 10 | Pending |
| E2E-05 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-09-10*
*Last updated: 2026-09-10 after initial definition*
