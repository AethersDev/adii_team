# Roadmap: ADII — Task A Investigator & Agent Runtime

## Overview

This brownfield roadmap preserves approved Task A Phases 1–5 as completed history and
organizes only the remaining deterministic investigator-runtime work. Phases 6–10 proceed
in fixed horizontal capability order: confirm and integrate Task B's controlled-tool
boundary, produce the shared structured decision, populate all supported dispositions,
harden failure handling, and verify Task A end to end. Tasks B, C, and D remain external
authorities; real external model-provider integration is deferred beyond this roadmap.

## Phase Order

- [x] **Phase 1: Fake Model / Provider** — Deterministic scripted provider (approved history)
- [x] **Phase 2: Minimal Investigator Loop** — Explicit-stop traced loop (approved history)
- [x] **Phase 3: Budget and Stopping Conditions** — Strict model-turn ceiling (approved history)
- [x] **Phase 4: Tool-call Orchestration** — Injected fake-tool flow and one-shot observations (approved history)
- [x] **Phase 5: Investigation State** — Immutable multi-step causal state (approved history)
- [ ] **Phase 6: Task B Real-tool Integration Checkpoint** — Confirm, then integrate the real controlled-tool boundary
- [ ] **Phase 7: Structured InvestigationDecision** — Return the existing shared decision contract
- [ ] **Phase 8: REPAIR / NO_REPAIR / ESCALATE Content** — Populate all three dispositions correctly
- [ ] **Phase 9: Reliability and Error Handling** — Attribute failures without weakening stop, budget, or trace guarantees
- [ ] **Phase 10: Task-A-only End-to-end Verification** — Verify the complete deterministic Task A runtime

Phases execute sequentially. Every implementation plan requires explicit approval before
execution, an automated requirements-verifier after implementation, and explicit final
approval before the next plan or phase begins.

## Completed Historical Capability

Phases 1–5 are closed and approved. They supply the baseline described by `HIST-01` through
`HIST-05` in `.planning/REQUIREMENTS.md`; they are not pending plans and will not be
redesigned or re-executed by this roadmap.

## Remaining Phase Details

### Phase 6: Task B Real-tool Integration Checkpoint

**Goal**: Connect Task A to Task B's real controlled-tool executor only after its callable
interface, ownership, and availability are confirmed.
**Depends on**: Approved Phase 5 and a confirmed Task B integration boundary
**Requirements**: INTG-01, INTG-02, INTG-03, INTG-04
**Current dependency status**: Blocked — the current branch contains only the
`02_src/adii/tools/` scaffold; no real Task B executor interface is available to confirm.
**Success Criteria** (what must be true):
  1. Repository and confirmed team evidence identify Task B's real executor, concrete
     callable interface, stability, and ownership—or record the exact missing dependency.
  2. No production integration begins while that interface is absent or unconfirmed.
  3. Once confirmed, the investigator invokes only the Task B controlled-tool boundary
     using the existing shared `ToolCall` and `ToolResult` types.
  4. Real-boundary tests preserve exact one-shot observations, accumulated state, logical
     turn accounting, all tool statuses, and contiguous trace sequences.
**Plans**: 2 plans, with Plan 06-02 unavailable until Plan 06-01 resolves the blocker

Plans:
- [ ] 06-01: Discover and document the Task B executor interface, availability, and blockers
- [ ] 06-02: Integrate and test the confirmed Task B executor boundary without owning Task B behavior

**Boundary notes**: Task A must not implement tools, schemas, permissions, SQL, or direct
environment access. Any need to change `02_src/adii/contracts/core.py` stops the plan for
separate cross-team review.

### Phase 7: Structured InvestigationDecision

**Goal**: Make normal Task A completion return the existing shared-contract
`InvestigationDecision` alongside the evidence needed to review how it was reached.
**Depends on**: Phase 6 approved
**Requirements**: DECI-01, DECI-02, DECI-03
**Success Criteria** (what must be true):
  1. A normally completed deterministic investigation returns an
     `InvestigationDecision`, not trace-only or free-text terminal output.
  2. The decision satisfies the current shared-contract invariants without shadowing or
     modifying the contract.
  3. Decision construction uses accumulated Task A investigation knowledge and does not
     perform validation, acceptance, evaluation, or scoring.
**Plans**: 2 plans

Plans:
- [ ] 07-01: Define and test the minimal deterministic decision-bearing terminal response within Task A
- [ ] 07-02: Integrate structured decision output with the loop while preserving trace, state, and budget behavior

**Boundary notes**: `InvestigationDecision` semantics come from the existing shared
contract. Ambiguity in that contract is a blocker, not permission for a local replacement.

### Phase 8: REPAIR / NO_REPAIR / ESCALATE Content

**Goal**: Populate contract-valid, evidence-grounded content for every supported
investigation disposition.
**Depends on**: Phase 7 approved
**Requirements**: DISP-01, DISP-02, DISP-03, DISP-04
**Success Criteria** (what must be true):
  1. REPAIR includes a non-empty root-cause explanation, repair ID, and bounded patch
     content accepted by the existing contract.
  2. NO_REPAIR explains why the condition is legitimate and includes no repair ID or patch.
  3. ESCALATE identifies the missing evidence or authority and includes no repair ID or patch.
  4. Deterministic tests reach all three dispositions without importing validation or evaluation.
**Plans**: 2 plans

Plans:
- [ ] 08-01: Implement and unit-test contract-valid content mapping for all three dispositions
- [ ] 08-02: Exercise evidence-dependent disposition production through the investigator loop

**Boundary notes**: A REPAIR disposition is a Task A proposal, never Task C acceptance.
No disposition may claim Task D evaluation or scoring authority.

### Phase 9: Reliability and Error Handling

**Goal**: Produce deterministic, correctly attributed failure outcomes while retaining
existing explicit-stop, budget, tool-observation, and tracing guarantees.
**Depends on**: Phase 8 approved
**Requirements**: RELI-01, RELI-02, RELI-03, RELI-04, RELI-05
**Success Criteria** (what must be true):
  1. Malformed model output is classified at the model/output boundary rather than escaping
     as an unclassified platform failure.
  2. Provider failure, scripted-provider exhaustion, explicit STOP, and turn-budget
     exhaustion remain structurally distinct.
  3. DENIED, REJECTED, and ERROR tool results remain distinct normal observations.
  4. Every owned failure path retains hard turn limits and an accurate contiguous trace.
**Plans**: 2 plans

Plans:
- [ ] 09-01: Define and test Task A's bounded failure classification and trace semantics
- [ ] 09-02: Integrate failure handling across provider, parsing, and tool-result paths without recovery scope expansion

**Boundary notes**: Task A may classify failures at its boundaries but must not absorb Task
B execution policy, Task C validation, or Task D scoring/reporting.

### Phase 10: Task-A-only End-to-end Verification

**Goal**: Demonstrate the complete deterministic Task A runtime through its controlled
external boundaries and stop at the structured decision boundary.
**Depends on**: Phase 9 approved and the confirmed Task B testable boundary
**Requirements**: E2E-01, E2E-02, E2E-03, E2E-04, E2E-05
**Success Criteria** (what must be true):
  1. Task-A-owned integration tests drive `IncidentContext` through deterministic provider
     turns, the confirmed Task B boundary, accumulated state, and a structured decision.
  2. Tests cover successful dispositions plus provider exhaustion, budget exhaustion,
     malformed output, and distinct tool-status paths owned by Task A.
  3. Architecture verification proves no direct filesystem, database, subprocess, network,
     validation, or evaluation access from the investigator.
  4. Focused tests, architecture tests, the full suite, Ruff, generated-status
     synchronization, and diff hygiene all pass without weakening Phase 1–5 tests.
  5. Verification stops at Task A's decision boundary and makes no Task C or Task D claims.
**Plans**: 2 plans

Plans:
- [ ] 10-01: Add deterministic Task-A integration scenarios covering success and owned failures
- [ ] 10-02: Run the final boundary, regression, generated-status, lint, and repository verification gate

**Boundary notes**: End-to-end means end of Task A, not end of validation, evaluation,
persistence, or reporting. External model-provider integration remains deferred to v2.

## External Dependencies and Authorities

| Track | Task A relationship | Blocking condition |
|-------|---------------------|--------------------|
| Task B | Supplies the real controlled-tool executor, schemas, permissions, and tool behavior | Phase 6 Plan 06-02 and Phase 10 real-boundary verification cannot proceed until its callable interface is confirmed |
| Task C | Independently validates proposed repairs | Any Task A requirement that would make the investigator accept or validate its own repair must stop for scope review |
| Task D | Owns evaluation, answer keys, scoring, persistence, and reporting | Task A tests and decisions must not claim or import this authority |
| Shared contracts | Supply cross-team values including `ToolCall`, `ToolResult`, and `InvestigationDecision` | Any required contract change needs separate cross-team approval before the affected plan proceeds |

## Progress

**Execution Order:** Phase 6 → Phase 7 → Phase 8 → Phase 9 → Phase 10

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Fake Model / Provider | Historical | Complete / approved | Before roadmap initialization |
| 2. Minimal Investigator Loop | Historical | Complete / approved | Before roadmap initialization |
| 3. Budget and Stopping Conditions | Historical | Complete / approved | Before roadmap initialization |
| 4. Tool-call Orchestration | Historical | Complete / approved | Before roadmap initialization |
| 5. Investigation State | Historical | Complete / approved | Before roadmap initialization |
| 6. Task B Real-tool Integration Checkpoint | 0/2 | Blocked on Task B interface confirmation | - |
| 7. Structured InvestigationDecision | 0/2 | Not started | - |
| 8. REPAIR / NO_REPAIR / ESCALATE Content | 0/2 | Not started | - |
| 9. Reliability and Error Handling | 0/2 | Not started | - |
| 10. Task-A-only End-to-end Verification | 0/2 | Not started | - |

---
*Roadmap initialized: 2026-09-10*
*Scope: Task A only; Phases 1–5 historical, Phases 6–10 remaining*
