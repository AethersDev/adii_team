# Proposal: the trace event contract (D-1)

**Status: proposed, 13 September 2026. Not agreed.** This is the first of the six week-2
decisions in [plan_telemetry.md](plan_telemetry.md), put in front of the team before any
constructor lands. Every event the loop, the tool layer and the validator emit will be built
through this vocabulary, and a vocabulary that grew by accident cannot be corrected later
without breaking archives.

The question is not *what should we log*. It is:

> **What facts must survive a run so that reporting, debugging, evaluation and later
> evidence citation never have to reconstruct what happened?**

## What stays fixed

`TraceEvent(sequence, kind, payload)` in `02_src/adii/contracts/core.py` is the envelope,
and this proposal does not change it. `sequence` is the identity of an event within a run.
A timestamp travels in the payload as `at` (ISO 8601, UTC). Two envelope fields were
considered and are not proposed: an `event_id` adds nothing to a contiguous `sequence`
inside one run, and an `actor` is implied by the kind. Either can be added later as a
reviewed contract change if a real use appears.

Three invariants the record enforces on every trace it accepts:

- `sequence` is contiguous from 0 and strictly increasing;
- every payload is finite JSON — already enforced;
- every `kind` is one of the kinds below, and its payload carries the fields that kind
  requires.

## The kinds

Requests and responses are different custody events. A request that never got its response
is a real state — a timeout, a crash — and it has to be representable without inventing a
turn that never completed.

| kind | emitted by | payload carries | why it exists |
|---|---|---|---|
| `run_started` | runtime | `incident_id`, `at` | the run began; the configuration it began under is on the record |
| `model_requested` | investigator | `turn`, `at`, `messages` — the messages added since the previous request; the full prompt is reconstructible from the trace | the transcript is caller-owned and what the model saw is part of the record (D1) |
| `model_responded` | investigator | `turn`, `at`, `content`, `usage` or null, `fingerprint` or null | one usage and one fingerprint slot per response; null is recorded, never omitted (D7, D15) |
| `tool_requested` | investigator | `call_id`, `name`, `arguments`, `at` | a `ToolCall`, verbatim |
| `tool_observed` | tool layer | `call_id`, `name`, `status`, `content`, `observation_id`, `at` | a `ToolResult`, verbatim, plus the identity a decision may later cite — minted here, never by the model (D2) |
| `submission_proposed` | investigator | `disposition`, `root_cause_id`, `repair_id`, `evidence_refs`, `at` | the terminal submission as the loop produced it, before the contract validated it — so a malformed answer is on the record, not a crash |
| `validation_completed` | validator | `accepted`, `at` | the verdict, from the other authority |
| `run_terminated` | runtime | `termination`, `detail`, `at` | how the run ended, in the loop's own controlled terms |

The walkthrough's five kinds map onto these — `incident_received` to `run_started`,
`tool_call` to `tool_requested`, `tool_result` to `tool_observed`, `decision_submitted` to
`submission_proposed`, `validation_completed` unchanged — and its fixture is rewritten in
the agreed vocabulary the day this is agreed. It is the only trace that exists, so the
cost of changing it is now zero and only rises.

## Observation identity, and citations

`tool_observed` mints `observation_id` — `obs-0004` for the observation at sequence 4 —
in the tool layer, bound to the trace. A decision cites observations by that id and by
nothing else:

```text
tool_requested → tool_observed → obs-0004 → decision cites obs-0004
→ the inspector resolves the citation to the exact trace event
```

This needs one contract change, which is why it is raised now rather than at M3:
`InvestigationDecision` gains `evidence_refs: tuple[str, ...]`, and where the record is
built every ref is checked against the observations the trace actually holds — the
contract cannot see the trace, so the record does the check. A citation to an id nobody
minted is rejected (D2). That change is a cross-boundary review for the four of us.
Nothing in D waits on it.

## How a run ends

`run_terminated.termination` is a closed set owned by the loop; `detail` is free text
beside it, never instead of it. Reporting preserves the classification and never
reinterprets it. The record today carries four values — `submitted`, `model_failure`,
`bound_hit`, `infrastructure_failure` — chosen from the outcomes D11 says the report must
label distinctly. The loop may need finer classes:

```text
completed · budget_exhausted · model_error · invalid_submission · tool_error · cancelled · internal_error
```

Which set is right is the investigator's call, made once, before the first run from the
loop is archived. What is not negotiable: a value outside the set is refused at
construction, and free text never stands in for the class.

## What is never in the record

The record is custody, not interpretation. No expected disposition, no answer-key
reference, no correctness, no evaluator state, and no evidence id that a tool did not mint.
If a field would let a reader of the archive know how the run *should* have gone, it
belongs to the evaluation authority and travels in a separate, hash-bound artefact.

## Done when

D-1 is complete only when this sequence runs end to end with a scripted adapter and no
live model:

```text
incident → model_requested → model_responded → tool_requested → tool_observed (obs id)
→ submission_proposed citing the id → validation_completed → run_terminated
→ RunRecord → archive → inspector
```

and the inspector renders that trace with no knowledge of the walkthrough. That is the
first genuine vertical skeleton of ADII.

## To agree

1. The kind set above, with the request/response split.
2. `observation_id` minted in the tool layer, and `evidence_refs` on the decision as a
   reviewed contract change.
3. The termination set, owned by the loop.
4. Timestamps in the payload; the envelope unchanged.
