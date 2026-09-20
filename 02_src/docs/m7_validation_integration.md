# Proposal: integrating independent validation without pretending every incident is rebuildable (M7)

**Status: proposed, 20 September 2026. Not agreed. No wiring lands before it is.**
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

Three rules the row fixes:

1. **NOT_CHECKABLE is not REJECT.** The proposal may be sound; the system lacks the world to
   know. No renderer colours or phrases it as validation failure.
2. **NOT_CHECKABLE is not "accepted anyway".** Admission is fail-closed: only ACCEPT is
   potentially admissible; REJECT and NOT_CHECKABLE are not admissible, and the recorded
   reason differs.
3. **A patch that cannot be applied is REJECT.** The rebuild is a check; `validator.py`
   names it in `checks_run` (`rebuild`) when `PatchRejected` fires, so the existing
   derivation reads it correctly. (C's file; one line.)

**Option A (recommended) — one additive field.** `ValidationResult` gains
`reason_code: str | None = None`: `None` for ACCEPT and REJECT, a closed set for
NOT_CHECKABLE — `no_rebuildable_world` now; `no_executable_transform` when packages carry
transforms the rebuild cannot yet run. The record serialises it; a record without the key
reads as `None`, so every archived run still loads. The reason is then read by type, never
parsed from prose — the rule this repository applies to every other classification.
Touches `contracts/`: **yes**, additive; and `adii.run_record/v1`, additive.

**Option B — no contract change.** NOT_CHECKABLE is `accepted=False, checks_run=()` and the
reason is the first token of `report`. Not recommended: it makes a prose field carry a code,
which is what row 1 of the trace contract exists to prevent.

**The page** phrases the three as: *accepted by the independent validator* · *rejected by
the independent validator* · *not checkable — this incident has no world the validator can
rebuild*; the third in the neutral colour of a fact, not the colour of a failure.

## Row 4 — Authorization stays separate

Authorization is the runtime's, decided before validation and recorded as its own fact:

```text
unauthorized = set(decision.patch) − set(context.permitted_write_paths)
trace event   repair_authorization {authorized: bool, unauthorized_paths: [...]}
```

The kind justifies itself by R0's trajectory — a REPAIR on an incident permitting no path,
today indistinguishable in the archive from an authorized one. The validator never sees
`permitted_write_paths`; the loop is not changed (the write-path gate of
`green_line.md` decision 5 is answered: *recorded by the runtime*, not refused by the loop
and not left to the validator).

**Independent, not sequential.** Validation is invoked for every REPAIR whether or not it is
authorized, and both facts land. Two reasons. The record's own invariant requires a verdict
on every submitted REPAIR (`record.py`: "a submitted REPAIR carries the validator's
verdict"), so skipping validation for an unauthorized patch would force a verdict that is
really an authorization result — the conflation this row exists to prevent. And the archive
is evidence: "unauthorized *and* would have been rejected" and "unauthorized *and* would
have passed" are different findings about a model. Admission is derived where it is
rendered — `authorized ∧ ACCEPT` — and stored nowhere, because nothing executes: no write
path exists in this milestone, and none is proposed. Touches `contracts/`: no.

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
3. A patch to a path not in `permitted_write_paths` records `repair_authorization
   {authorized: false, unauthorized_paths: [...]}` **and** its validation fact.
4. A patch that cannot be applied renders REJECT, with `rebuild` among the checks.
5. `NoValidatorYet` is gone; "No independent validator exists yet" appears in no new record.
6. The page shows the three verdicts in three phrasings; NOT_CHECKABLE is not a failure
   colour; the authority line is read from the trace.
7. Guards: `adapter_translates_only_unknown_incident`, `not_checkable_is_not_accepted`,
   `authorization_is_recorded_for_every_repair`, `validator_never_sees_permitted_paths`.

## Decision record

Four decisions, not four discussions. Each row ends in exactly one of three states —
`APPROVED`, `REVISE` (with what changes) or `DEFER` (with what it waits on). A contract
change takes all four names. The resolution is recorded in a **new commit**; this file's
history is proposal, then review, then decision, then implementation.

| # | Decision | What must be fixed before code | Touches `contracts/` | Decided | By |
|---|---|---|---|---|---|
| 1 | Where validation is invoked | in `run_incident`'s existing slot, through a runtime adapter that translates `UnknownIncident` and nothing else; `NoValidatorYet` deleted | no | open | |
| 2 | Supported vs unsupported worlds | the validator's registry, asked by attempt; `UnknownIncident` is the answer; no second query | no | open | |
| 3 | ACCEPT / REJECT / NOT_CHECKABLE | the table above; NOT_CHECKABLE is neither REJECT nor admissible; a failed rebuild is REJECT; Option A (`reason_code`) or Option B | **yes** (A) / no (B) | open | |
| 4 | Authorization apart from validation | runtime-owned, recorded as `repair_authorization`, evaluated for every REPAIR independently of validation; admission derived, nothing executed | no | open | |
