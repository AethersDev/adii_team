# Proposal: integrating independent validation without pretending every incident is rebuildable (M7)

**Status: proposed 20 September 2026, revised on the advisor's review 20–21 September. Not agreed — C marks the four rows. No wiring lands before they are.**
The validator exists (M6, `02_src/adii/validation/`) and rebuilds one world. The live
runtime still hands every REPAIR to `NoValidatorYet`. Between the two sits a decision the
code must not make on its own: what a REPAIR's verdict *is* when the world it patches
cannot be rebuilt. This file decides that, and only that.

**For the reviewer.** Read this file, then `run_incident` in `02_src/adii/runtime/run.py`,
`validate()` in `02_src/adii/validation/validator.py`, and `ValidationResult` in
`02_src/adii/contracts/core.py`. Then decide the four rows at the end. The question is not
*how do we validate the demo incident* — it cannot be validated yet, and this proposal
does not pretend otherwise. It is:

> **How does a REPAIR cross into the runtime's admission without a validator PASS ever
> meaning permission, and without "we could not check this" ever being said as
> "this failed" or "this passed"?**

## What is true today

- `run_incident` calls `validator.validate(context, decision)` for every REPAIR and records
  `validation_completed {accepted}`. Any exception the validator raises is caught by its
  `except Exception` and the run ends as `infrastructure_failure`.
- The validator (C) is strict about what it can rebuild: `_WORLD_BUILDERS` holds
  `demo-learning-001`; every other `incident_id` raises `UnknownIncident`. Wired as it is,
  every live REPAIR on the six specimens and on every uploaded CSV would end as an
  infrastructure failure — worse than the placeholder it replaces.
- `ValidationResult(accepted, report, checks_run)` has two states by contract and three by
  convention: `render.py` and `phrasing.js` both derive `ACCEPTED` when accepted, `REJECTED`
  when `checks_run` is non-empty, else `UNCHECKED` ("not checked by a validator").
- `validator.py` answers a patch that cannot be applied (`PatchRejected`) with
  `accepted=False, checks_run=()`. Under the convention above that reads *unchecked*, not
  *rejected*. A collision, not yet visible because nothing is wired.
- `permitted_write_paths` is enforced nowhere. R0 archived a REPAIR on an incident that
  permitted no path; 41-2 and `revenue-after-deploy-qwen4b-smoke-1` proposed patches to
  `transforms/revenue_daily.sql` in worlds where no such transform exists.

## The shape

Three facts about a REPAIR, each established by a different authority, none implying
another, all recorded:

```text
terminal REPAIR
    │
    ├── AUTHORIZATION   (runtime)        patch keys ⊆ permitted_write_paths ?
    │                                     → authorized | unauthorized (paths named)
    │
    └── VALIDATION      (adapter → C)    world rebuildable ?
              ├── yes → Validator.validate → ACCEPT | REJECT   (checks named)
              └── no  → NOT_CHECKABLE  reason_code = no_rebuildable_world
                                                    │
                                          ADMISSION (derived, never stored)
                                          authorized ∧ ACCEPT → potentially admissible
                                          anything else       → not admissible
                                          EXECUTION: not performed — no write path exists
```

```text
AUTHORIZED  ≠  VALID  ≠  CHECKABLE
```

**Authorization and validation answer independent questions about the same submitted
proposal. Neither gates whether the other fact may be established. Admission is derived
from both.** That sentence is the architecture; the rows below are its consequences.

## Row 1 — Where validation is invoked

Where it is invoked already: `run_incident`, through the `Validator` slot, for a REPAIR and
nothing else. What changes is the object in the slot. `runtime/__main__.py` hands in a
**runtime adapter** — one class in `runtime/validation.py`, satisfying `runtime.run.Validator`
— that holds `validation.validator.Validator()` and translates exactly one exception:

```text
adapter.validate(context, decision)
    try:    return validator.validate(context, decision)        # ACCEPT | REJECT, verbatim
    except UnknownIncident:  return NOT_CHECKABLE(no_rebuildable_world)
    (anything else propagates: an infrastructure failure, as today)
```

The validator is not weakened: `validate()` keeps raising for a world it cannot rebuild, its
inputs stay a frozen world and a candidate patch, and it learns nothing of permitted paths,
evidence, scoring or keys. `NoValidatorYet` is deleted, and with it the sentence "No
independent validator exists yet", which no new record carries. Touches `contracts/`: no.

## Row 2 — Supported and unsupported worlds

The validator's own registry is the single source of truth, and it is asked by attempt:
`UnknownIncident` (public, in `validation/validator.py`) *is* the answer "not rebuildable".
A separate `supports(incident_id)` query was considered and is not proposed: two places
would then say what the validator can do, and they would drift.

Today the registry holds `demo-learning-001`. It grows by one entry per world the validator
can rebuild — configuration A of the canonical world (`01_data/demo/world/README.md`) is
the first product-grade one, when its transform-bearing package exists and a rebuild can
execute it. Until then the six specimens and every upload are unsupported, and say so as
NOT_CHECKABLE, never as a failure of ours. Touches `contracts/`: no.

## Row 3 — ACCEPT, REJECT, NOT_CHECKABLE

| verdict | meaning | `accepted` | `checks_run` | `reason_code` |
|---|---|---|---|---|
| ACCEPT | the world was rebuilt with the patch applied and every check passed | true | the checks | none |
| REJECT | the rebuild or a check failed — a finding about the repair | false | the checks, the rebuild among them | none |
| NOT_CHECKABLE | no world to rebuild — **not a finding about the repair** | false | empty | `no_rebuildable_world` |

Three facts that look alike and are not, fixed here so no code conflates them:

```text
the candidate cannot be rebuilt, because the candidate is invalid   → REJECT, "rebuild" in checks_run
the validator cannot rebuild, because its machinery failed          → infrastructure_failure
the validator has no rebuild definition for this incident           → NOT_CHECKABLE, no_rebuildable_world
```

Three rules the row fixes:

1. **NOT_CHECKABLE is not REJECT.** The proposal may be sound; the system lacks the world to
   know. No renderer colours or phrases it as validation failure.
2. **NOT_CHECKABLE is not "accepted anyway".** Admission is fail-closed: only ACCEPT is
   potentially admissible; REJECT and NOT_CHECKABLE are not admissible, and the recorded
   reason differs.
3. **A patch that cannot be applied is REJECT.** The rebuild is a check; `validator.py`
   names it in `checks_run` (`rebuild`) when `PatchRejected` fires. A candidate-caused
   rebuild failure is a finding about the candidate and never masquerades as "the
   validator never ran". (C's file; one line.)

**The representation: one additive field.** `ValidationResult` gains
`reason_code: str | None = None`: `None` for ACCEPT and REJECT, a closed set for
NOT_CHECKABLE — `no_rebuildable_world` now; `no_executable_transform` when packages carry
transforms the rebuild cannot yet run. The record serialises it; a record without the key
reads as `None`, so every archived run still loads. The reason is read by type, never
parsed from prose. Encoding the reason as the first token of `report` was considered and
rejected: `report` is prose, and a prose field must never become a hidden protocol.
Touches `contracts/`: **yes**, additive; and `adii.run_record/v1`, additive.

**One canonical derivation of the state**, beside the contract as a property of the
result, used by the runtime, `render.py` and the page alike (the page's copy of the rule is
held equal to it by a test, as the evidence-bundle names are):

```text
reason_code is not None                 → NOT_CHECKABLE
accepted                                → ACCEPT
not accepted and checks_run non-empty   → REJECT
otherwise                               → UNCHECKED  — legacy only
```

The derivation reads; it does not forgive. The **state space is closed** — four shapes are
valid, and a result in any other shape is not a verdict with an odd label but an invalid
object, refused where it is built:

```text
ACCEPT            accepted=True   reason_code=None                    checks_run any (the checks that passed)
REJECT            accepted=False  reason_code=None                    checks_run non-empty (the rebuild among them)
NOT_CHECKABLE     accepted=False  reason_code="no_rebuildable_world"  checks_run=()
UNCHECKED legacy  accepted=False  reason_code=None                    checks_run=()   loadable only; never produced
anything else     → invalid ValidationResult → infrastructure_failure
```

So `accepted=True` with a `reason_code`, a `reason_code` beside checks that ran, or an
`accepted=True` with no checks and nothing to say cannot travel: the precedence rule above
would otherwise read a label off an impossible object and hide it. `UNCHECKED` exists so
that every archived record (`accepted=false, checks_run=(), reason_code` absent — the
placeholder's shape) keeps loading and reading as it always has; **no wired validation may
ever produce that shape**: the adapter refuses to return it (an infrastructure failure,
ours), and a test holds the refusal. Where the closure is enforced — the contract's
constructor, for every shape but the legacy one, which archived records must still pass —
is C's and the contract's call; the algebra is the decision.

**The page** phrases the three as: *accepted by the independent validator* · *rejected by
the independent validator* · *not checkable — this incident has no world the validator can
rebuild*; the third in the neutral colour of a fact, not the colour of a failure.

## Row 4 — Authorization stays separate

Authorization is the runtime's, and its own fact:

```text
unauthorized = set(decision.patch) − set(context.permitted_write_paths)
authorized   = unauthorized == ∅          (the offending paths named when not)
```

It is recorded as a structured authorization fact of its own, never encoded as validation.
**Its canonical trace representation follows D-1** (`trace_event_contract.md`, open): a new
event kind — `repair_authorization` was the candidate — would settle a vocabulary question
this proposal has no standing to settle, so the fact's representation is deferred to that
decision and nothing here pre-empts it. Until D-1 resolves, no authorization fact is
recorded and the page says nothing about permission, as today. The validator never sees
`permitted_write_paths`; the loop is not changed (the write-path gate of `green_line.md`
decision 5 is answered in substance: *recorded by the runtime*, not refused by the loop and
not left to the validator; its recording waits on D-1).

**Independent, not sequential.** Validation is invoked for every REPAIR whether or not it is
authorized, and both facts land. Two reasons. The record's own invariant requires a verdict
on every submitted REPAIR (`record.py`: "a submitted REPAIR carries the validator's
verdict"), so skipping validation for an unauthorized patch would force a verdict that is
really an authorization result — the conflation this row exists to prevent. And the archive
is evidence: *unauthorized and REJECT*, *unauthorized and ACCEPT*, *unauthorized and
NOT_CHECKABLE* are three different findings about a model, all inadmissible for different
reasons. Admission is derived where it is rendered — `authorized ∧ ACCEPT` — and stored
nowhere: it is not a third authority, and nothing executes — no write path exists in this
milestone, and none is proposed.

**Independence is not access.** An unauthorized target grants the validator nothing: it
rebuilds only inside its disposable frozen world, only over the bounded patch
representation, and a patch's target stays a logical name in that world — never
filesystem authority, whatever the model wrote. Touches `contracts/`: no.

## Out of scope, on purpose

The canonical A/B/C world and its package; a rebuild that executes a package's transforms;
checks expressed from a world's declared operational contract rather than from knowledge of
`orders`/`mart_daily`; executing any repair; scoring an unchecked or unauthorized REPAIR
(`green_line.md` decision 3, the evaluation authority's).

## The acceptance test, fixed before the code

1. A local model's REPAIR on `demo-learning-001` ends ACCEPT or REJECT with checks named —
   the first REPAIR to cross the whole runtime into a real verdict.
2. A REPAIR on `revenue-after-deploy` (or any upload) ends NOT_CHECKABLE with
   `reason_code = no_rebuildable_world` — never `infrastructure_failure`.
3. A patch that cannot be applied renders REJECT, with `rebuild` among the checks.
4. A validator that raises anything but `UnknownIncident` ends the run as
   `infrastructure_failure` — the adapter sanitises nothing.
5. The adapter never returns the legacy combination (`accepted=false`, no checks, no
   reason); every archived record still loads and still reads `UNCHECKED`.
6. `NoValidatorYet` is gone; "No independent validator exists yet" appears in no new record.
7. The page shows the three verdicts in three phrasings from the one derivation;
   NOT_CHECKABLE is not a failure colour.
8. Every combination outside the four shapes is refused as an invalid result — `accepted`
   with a `reason_code`, a `reason_code` beside checks that ran — never read as a verdict.
9. Guards: `adapter_translates_only_unknown_incident`, `not_checkable_is_not_accepted`,
   `wired_validation_never_returns_the_legacy_shape`, `rebuild_failure_is_a_check`,
   `validation_result_shapes_are_closed`.
10. *Following unit, once D-1 names the representation:* a patch outside
   `permitted_write_paths` records the authorization fact **and** its validation fact;
   guard `validator_never_sees_permitted_paths`.

## Review, 20 September (advisor)

| # | mark | what changed in this text |
|---|---|---|
| 1 | APPROVED | — |
| 2 | APPROVED | — |
| 3 | REVISE → the additive `reason_code`; one canonical state derivation shared by runtime, renderer and page; the legacy `UNCHECKED` kept for archived records and never produced by wired validation; the three look-alike facts fixed; **21 Sep:** the state space closed — four valid shapes, every other combination an invalid result, so the derivation never reads a label off an impossible object | all folded in above |
| 4 | semantics APPROVED; representation REVISE → the authorization fact's trace form is D-1's to decide, not this row's; the independence principle stated as architecture; independence is not filesystem access | folded in above; the `repair_authorization` kind withdrawn to D-1 |

The first implementation unit, once C marks the rows: `reason_code`; the canonical
derivation; the rebuild named as a check; the runtime adapter; `demo-learning-001` to the
real validator; unknown incident to NOT_CHECKABLE; `NoValidatorYet` removed; tests for all
three states and the infrastructure failure. Authorization follows as its own bounded unit
when D-1 names its representation. A/B/C is not in either unit: the point of the first is
that **the live runtime has a real independent validator for the first time**; A then
joins a mechanism that already works.

## Decision record

Four decisions, not four discussions. Each row ends in exactly one of three states —
`APPROVED`, `REVISE` (with what changes) or `DEFER` (with what it waits on). A contract
change takes all four names. The resolution is recorded in a **new commit**; this file's
history is proposal, then review, then decision, then implementation.

| # | Decision | What must be fixed before code | Touches `contracts/` | Decided | By |
|---|---|---|---|---|---|
| 1 | Where validation is invoked | in `run_incident`'s existing slot, through a runtime adapter that translates `UnknownIncident` and nothing else; `NoValidatorYet` deleted | no | open | |
| 2 | Supported vs unsupported worlds | the validator's registry, asked by attempt; `UnknownIncident` is the answer; no second query | no | open | |
| 3 | ACCEPT / REJECT / NOT_CHECKABLE | the table above; NOT_CHECKABLE is neither REJECT nor admissible; a failed rebuild is REJECT; additive `reason_code`; one canonical derivation over a closed set of four shapes, the legacy one loadable and never produced | **yes**, additive | open | |
| 4 | Authorization apart from validation | runtime-owned, its own structured fact, evaluated for every REPAIR independently of validation; admission derived, nothing executed; the fact's trace representation deferred to D-1 | no | open | |
