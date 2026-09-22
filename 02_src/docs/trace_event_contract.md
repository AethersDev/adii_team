# Proposal: the trace event contract (D-1)

**Status: proposed, 13 September 2026. Not agreed. No constructor lands before it is.**
This is the first of the six week-2 decisions in [plan_telemetry.md](plan_telemetry.md).
Every event the loop, the tool layer and the validator emit will be built through this
vocabulary, and a vocabulary that grew by accident cannot be corrected later without
breaking archives. The branch pauses here on purpose: before disagreement becomes code.

**For the reviewer.** Read this file, then the affected types in
`02_src/adii/contracts/core.py`, then decide only the four rows in the decision record at
the end. Nothing else needs reading first. The question is not *what should we log*. It is:

> **What facts must survive a run so that reporting, debugging, evaluation and later
> evidence citation never have to reconstruct what happened?**

## The envelope stays fixed

`TraceEvent(sequence, kind, payload)` in `contracts/core.py` is the envelope, and this
proposal does not change it. Two fields were considered and are not proposed: an
`event_id`, because `(run label, sequence)` is already a stable compound identity — the
label is immutable and the sequence is contiguous — and adding a second identifier would
give one object two names without a demonstrated need; and an `actor`, because the kind
implies it. If events are ever referenced from outside their run, that is the moment to
reconsider, as a reviewed contract change.

Three invariants the record enforces on every trace it accepts:

- `sequence` is contiguous from 0 and strictly increasing;
- every payload is finite JSON — already enforced;
- every `kind` is one of the kinds below, and its payload carries the fields that kind
  requires.

## Two identities, kept apart

`sequence` identifies a **trace event**. `observation_id` identifies an **evidence object
the tool layer produced**. They are different things and must never be derived from each
other: the tool layer keeps its own counter and mints `obs-0001`, `obs-0002`, … for each
observation it returns, unique within the run, and only a `tool_observed` event carries
one. A submission cites observations by `observation_id` and nothing else, so a citation
can resolve only to an actual observation, never to an arbitrary trace event.

```text
tool_requested → tool_observed(obs-0002) → submission cites obs-0002
→ the inspector resolves the citation to that observation's exact trace event
```

## The rule for adding a kind

**Every event kind must justify its existence with a trajectory it disambiguates** — a
failure, or a reconstruction, that becomes ambiguous without it. If a kind cannot name one,
it is not added. Requests and responses are separate kinds under this rule:

```text
model_requested → provider timeout → no model_responded   → run_terminated(model_failure)
tool_requested  → tool error       → no tool_observed     → the trace shows the request
```

Neither trajectory is representable with a single `model_turn` or `tool_call` event without
inventing a turn that never completed.

## The kinds

| kind | emitted by | payload carries | the trajectory that justifies it |
|---|---|---|---|
| `run_started` | runtime | `incident_id`, `at` | a run that began and produced nothing else still leaves a record of having begun; the configuration it began under is on the record |
| `model_requested` | investigator | `turn`, `at`, `messages` — the messages added since the previous request; the full prompt is reconstructible from the trace | a request with no response is a timeout or a crash, and must be distinguishable from a turn that completed (D1: the transcript is caller-owned) |
| `model_responded` | investigator | `turn`, `at`, `content`, `usage` or null, `fingerprint` or null | one usage and one fingerprint slot per response; a null is recorded, never omitted, so a backend change mid-run is visible (D7, D15) |
| `tool_requested` | investigator | `call_id`, `name`, `arguments`, `at` | a `ToolCall`, verbatim: a request the tool layer refused or never answered still happened |
| `tool_observed` | tool layer | `call_id`, `name`, `status`, `content`, `observation_id`, `at` | a `ToolResult`, verbatim, plus the identity a decision may later cite — minted here, never by the model (D2); `DENIED`, `REJECTED` and `ERROR` are observations too |
| `submission_proposed` | investigator | `disposition`, `root_cause_id`, `repair_id`, `evidence_refs`, `at` | the terminal submission as the loop produced it, before the contract validated it — so a malformed answer is on the record as a scored failure, not a crash (M4) |
| `validation_completed` | validator | `accepted`, `at` | the verdict, from the other authority, distinguishable from the agent's own rehearsal |
| `run_terminated` | runtime | `termination`, `detail`, `at` | how the run ended, in the loop's own controlled terms; without it a truncated archive and a completed run look the same |

The walkthrough's five kinds map onto these — `incident_received` to `run_started`,
`tool_call` to `tool_requested`, `tool_result` to `tool_observed`, `decision_submitted` to
`submission_proposed`, `validation_completed` unchanged — and its fixture is rewritten in
the agreed vocabulary the day this is agreed. It is the only trace that exists, so the cost
of changing it is zero today and only rises.

## Timing

Ordering is `sequence`, never the clock. `at` (ISO 8601, UTC, from the runtime's clock) is
in every payload because latency and the wall-clock bound are measured from the trace, not
self-reported (M8, D9). It is evidence of *duration*, not of *order*, and two events with
equal or inverted timestamps are not an error.

## Citations need one contract change

`InvestigationDecision` gains `evidence_refs: tuple[str, ...]`. The contract cannot see the
trace, so where the record is built every ref is checked against the observations the trace
actually holds; a citation to an id nobody minted is rejected (D2). This is raised now
rather than at M3 because it is the one place the vocabulary reaches into the shared
contracts, and it takes all four names. Nothing in D waits on it.

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

## The acceptance test, fixed before the code

D-1 is complete only when this sequence runs end to end from a **scripted adapter** — no
live model — and every assertion below holds:

```text
scripted incident
→ run_started
→ model_requested → model_responded
→ tool_requested  → tool_observed(obs-0001)
→ model_requested → model_responded
→ submission_proposed(evidence_refs=["obs-0001"])
→ validation_completed
→ run_terminated
→ RunRecord → archive → inspector
```

```text
✓ sequence is contiguous from 0
✓ every kind is in the vocabulary and every payload carries its required fields
✓ obs-0001 is minted exactly once, by the tool layer, and only on a tool_observed event
✓ evidence_refs resolve to observations within the same run
✓ a fabricated evidence_ref is rejected where the record is built
✓ no evaluator or answer-key field enters the trace
✓ the inspector renders the run from the RunRecord alone, with no knowledge of the script
```

Once the decisions below are made, D-1 has almost no design freedom left — only
implementation.

## Observed implementation, 14 September: three vocabularies side by side

A's loop merged into main on 14 September (PR #12) with a trace vocabulary of its own. D-1
is therefore no longer a choice of names. It is the integration contract that decides
whether A can enter the runtime without producing two competing histories of one run.
Three vocabularies now exist: the walkthrough's five kinds, which the runtime's `Recorder`
writes today; the eight proposed above; and the eight A emits. This section records what
the implementation shows, event by event, so the review is about information lost, not
about taste.

### What A emits, and what each kind actually means

Read from `02_src/adii/investigator/loop.py`, not from its docstrings.

| A emits | when, exactly | what it means | treatment to review |
|---|---|---|---|
| `model_turn` | only when a response is none of a tool call, a decision or a stop | a successful plain-text response, and nothing else | not the canonical model event; replace with explicit request and response events |
| `tool_call` | after a response parses as a tool call, before dispatch; carries `incident_id`, `turn_index`, `call_id`, `name`, `arguments` | a request to use a tool | a durable execution event |
| `tool_result` | after the executor answers; carries the result's `status` and `content` | B's observation reached the loop | a durable observation event; B's `evidence_id` inside `content` is the observation identity, preserved and never re-minted |
| `decision_submitted` | after a decision parses and passes the evidence gate; carries the whole decision | the terminal submission | a durable submission event — and it closes the gap where a validator crash lost the decision, since the record's trace would carry it |
| `decision_rejected` | when a decision fails to parse, fails the contract, or fails the evidence gate; the loop continues | a submission that did not stand | open: its own event, or an outcome attached to a submission event (row 6) |
| `loop_stopped` | on the explicit stop signal, with no decision | the loop ended; what that means is undecided | a termination — the one ending the implementation reports without saying what it means (row 5) |
| `budget_exceeded` | immediately before `TurnBudgetExceededError` is raised | the turn budget ended the run | a termination classification, not a peer event |
| `provider_failure` | immediately before `ProviderFailureError` is raised, the reason redacted of credentials | the provider ended the run | a termination classification, not a peer event |

Two questions for every kind: does it represent something that must survive the run, and
if so, is it an event or a termination classification. The last three rows answer the
second by their position in the code: each is written once, right before the loop leaves.

### The proof obligation the request/response split now carries

The loop calls the provider with no event beforehand. So a turn that ends in a tool call
leaves `tool_call` and `tool_result` and no model event; a turn that decides leaves only
the decision event; a request that fails leaves only `provider_failure`. From that trace a
request that failed cannot be told apart from a request never made, model turns cannot be
counted without knowing which kinds imply one, and a response that became a tool call is
not recorded as a response at all. That is the evidence for `model_requested` and
`model_responded` as separate events — from the implementation, not from preference.

The adapter must record the response at the provider boundary, before A parses it into a
tool call, a decision, a stop or plain text. Inferring `model_responded` afterwards from
the parsed outcome would be the same reconstruction under better names.

### The target trajectories

```text
a completed run              a provider failure          a budget
model_requested              model_requested             …
model_responded              run_terminated              model_requested
tool_requested                 (provider_failure)        run_terminated
tool_observed (obs_N)                                      (budget_exhausted)
model_requested
model_responded
decision_submitted
run_terminated (completed)
```

No synthetic failure event is needed to explain why a run ended: the termination carries
the classification, preceded by whatever request makes it intelligible.

### The ownership the review approves or rejects

```text
the provider boundary   →  model_requested, model_responded
A                       →  interprets the response: tool request, decision, stop
B                       →  mints the observation identity
the runtime boundary    →  maps A's endings to the canonical termination
RunRecord               →  preserves the one resulting trace
```

Explicitly not this: A's trace and the runtime's trace, merged afterwards into the record.
A record reconstructed from two partial authorities is two histories under one label. A
keeps its own exceptions, `TurnBudgetExceededError` and `ProviderFailureError`, as part of
its execution API; the runtime boundary maps them to termination classes in two lines.
`Terminated` moves into the shared contracts only if more than one independent package
must produce the same object, never to make that wiring look tidier.

### The live spike is not evidence for the rows, only for the seam

Branch `spike/live-local` (15 September) drives A's loop from the runtime with a local
model behind A's `respond()` seam. To make a run possible at all it had to pick names for
the provider-boundary events and a class for a stop without a decision; it uses this
proposal's names as placeholders and maps the stop to `model_failure` with the detail
saying so. Those choices are the spike's, not the team's. What the spike does establish
is narrower and real: A's seam can drive a model, and recording at the provider boundary
before A parses the reply is possible with no change to A. It was meant to stay on its
branch until rows 1 to 6 were resolved; it reached `main` on 16 September with the live
console. Its placeholders are therefore what `--provider local` records today, marked
SPIKE in the code, and whatever the rows decide replaces them in place (D-6b). A run
made through them is a run of the console, not evidence about ADII — see
`green_line.md`.

### What is genuinely open

Three questions, not eight names competing equally: the canonical names and envelopes for
model request, model response, tool request, tool observation, and decision submission or
rejection (rows 1–4); the meaning of a stop without a decision (row 5); and whether a
rejection is its own event or an outcome on a submission (row 6).

## Decision record

Four decisions, not four discussions. Each row ends in exactly one of three states —
**Evidence since the proposal, 14 September.** Row 2: B's executor
(`02_src/adii/tools/executor.py`) mints an id per OK observation, named `evidence_id`, a
hash of the tool, its arguments and its content — not the sequence number. Row 4: the
runtime measures latency around the run with a monotonic clock and records nothing per
event. The termination set lives in code as `runtime.run.Terminated`, raised by the loop.
None of this resolves a row; it is what the deciders now have in front of them.

`APPROVED`, `REVISE` (with what changes) or `DEFER` (with what it waits on) — never "looks
good" or "probably". A contract change takes all four names.

When the rows are filled, the resolution is recorded in a **new commit**. This file's
history is proposal, then review, then decision, then implementation; rewriting an earlier
commit to make the proposal look as if it always held the final answer would destroy the
one part of that history worth keeping.

| # | Decision | What must be fixed before code | Touches `contracts/` | Decided | By |
|---|---|---|---|---|---|
| 1 | Event vocabulary | the exact closed set of kinds above, and what each means | no | open | |
| 2 | Observation identity | the tool layer mints `observation_id`; unique within a run; never derived from `sequence` | no | open | |
| 3 | Decision citations | `evidence_refs` enters `InvestigationDecision` now, checked against the trace where the record is built | **yes** | **decided 22 Sep** — `evidence_refs: tuple[str, ...]` on `InvestigationDecision`: the evidence ids the tool layer minted, each cited once (the contract's invariant). Every cited id must exist in this run, resolve to an observation the model received, and come from a successful governed tool result: the loop's evidence gate refuses any other as `decision_rejected` (class `evidence_gate`, the ids named, the reason returned once — row 6), and a record is never built citing what its trace never minted (an investigator that reaches the runtime with one is our defect, archived as such). A correct disposition with invalid or missing citations is not a grounded success: the evaluation report carries grounding beside the category, never inside it. A citation proves the evidence existed and was available to the model; whether it warrants the conclusion is the evaluation authority's question, a grounding key's. NO_REPAIR and ESCALATE cite the same way; the minimum-observation rule is unchanged. The decision structure does not separate diagnosis from action, so one list serves both and nothing more enters the schema | project owner, 22 Sep 2026, after advisor review |
| 4 | Event timing | `at` in every payload, from the runtime's clock, evidence of duration only; `sequence` orders | no | open | |
| 5 | A stop without a decision | A's `<STOP>` ends the loop with no decision. The record allows no decision; it lacks a truthful termination class for this ending. Candidates: `intentional_stop_no_decision`, `invalid_stop`, `incomplete` — which is right depends on whether the stop is a legitimate outcome or only permission to stop trying. The adapter must not choose | no | open | |
| 6 | Rejection: event or outcome | `decision_rejected` as its own durable event, or an outcome attached to a submission event | no | **decided 22 Sep** — its own durable event: `{incident_id, turn_index, rejection_class ∈ invalid_envelope · invalid_decision · evidence_gate, reason (bounded), submission_sha256, submission_chars}`; any reply that is none of the three forms is one, no form special-cased, nothing reinterpreted as a decision; the loop emits it into the runtime's recorder as it happens — the runtime owns the one execution record, the loop returns no second history that is translated or discarded; the reason is returned to the model once with the next request, under the existing bounds | D, on the advisor's review; the loop's owner to object |
| 7 | The authorization fact's event | m7 row 4 (built 22 Sep) records `RepairAuthorization` in the record for every REPAIR; whether the fact is also an event — `repair_authorization` was the candidate — is this contract's to name | no | open | |
