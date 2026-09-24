# The final plan — from this tree to final day, in phases

**Written 23 September 2026. The execution plan for the line in
[release_evidence.md](release_evidence.md) §6, which stays the decision. The team's tracks
are delivered; from here one architect and one coding agent close the system in the
phases below, each finished before the next begins. Nothing is started that cannot be
finished inside its phase, and nothing half-built reaches `main`.**

Two dates parameterise the plan: **D**, demo day, and **P**, the partner session three days
later. The submission deadline is 18 October, and the submission is a ZIP upload.

Engineering throughput is not what bounds this plan. The remaining code is closure work in
small units behind tests, guards and contracts, and a coding agent writes it as fast as it
can be reviewed. What bounds it is listed in "What sets the pace", near the end: the
decisions only the architect can mark, the freeze order, one paid pack, one Windows
qualification, and the calendar the film is shot on.

## The one question

Every unit answers it before it starts, or waits:

> Does this increase the truth, the legibility, or the defensibility of what is shown on
> final day?

## How the two of us work

- **One unit, one branch, one merge.** The architect merges after the local gate below
  is green on the Mac. `main` never carries a half-built unit.
- **The local gate, on every unit.** The relevant tests run before a change so what was
  already failing is known; after it, `python -m ruff check 02_src`, `python -m pytest`
  (the browser tests included, with Chrome present), the two syncs
  (`sync_briefing.py`, `sync_status.py`), and `python 02_src/scripts/guard_check.py --only
  <track>` for every track touched. A new guard is not done until its row is in the
  registry and the pass reports it killed. The full guard pass runs before the freeze.
- **CI is optional assistance, not a gate.** The bootcamp grades the submitted ZIP, not
  GitHub Actions. Cross-platform correctness is established by qualifying the exact
  submission artefact on a clean Windows machine and a clean Mac (phases 4 and 7), which
  is the test that matters: a developer checkout is not what the panel receives.
- **Money is spent once.** Only on the final paid pack in phase 5, and the live run on
  stage. No exploratory smokes, no transitional runs, no model comparisons, no repeated
  spend checks. Every rehearsal runs on the local model, which costs nothing.
- **Decisions before code.** A row in the table at the end of this file is marked
  `APPROVED`, `REVISE` or `DEFER` in its own commit before the unit that depends on it is
  built. The proposals it resolves are never amended to look as if they always held the
  answer ([trace_event_contract.md](trace_event_contract.md),
  [m7_validation_integration.md](m7_validation_integration.md),
  [development_catalog.md](development_catalog.md)).
- **Net line delta reported per unit.** Deleting is progress. A unit that adds more than it
  removes says why.
- **Sacred, from §6:** frozen evaluation evidence, archived runs, scored protocols. Not
  sacred: the prototype page, the specimen layout, the demo narrative, development fixtures.
- **Nothing is quoted that a record does not hold.** The prototype's runs, the 48-run
  census and the predecessor's 18/18 are engineering history
  ([inherited/CONTROLS.md](inherited/CONTROLS.md)), never on the stage.

## The phases at a glance

```text
0  MERGE AND BASELINE          the branch to main; CI demoted; the archive attested
1  CLOSE THE SEAMS             judge · grounding · row 1 · row 5 · world A
2  THE DEVELOPMENT SET         six geometries as packages; keys frozen first
3  CONTROLS AND MEASUREMENT    two arms · grid runner · semantics v2 · report
4  FREEZE                      one digest for everything measured; Windows qualified
5  THE BENCHMARK               local rehearsal · one pre-flight · the paid pack once
6  REPORT AND PRODUCT SURFACE  the evaluation report; the benchmark on the page
7  PRESENTATION, FILM, SUBMIT  deck · live script · film · the ZIP qualified
```

A phase ends at its gate, not on a date.

Phase 7's deck and script are written in parallel with phases 5 and 6; only the film and
the rehearsals wait for the frozen build.

---

## Phase 0 — Merge and baseline

**Goal.** The code that fixed the last paid run's two blockers is on `main`, and the
archive is attested, so every later receipt names the revision that actually ran.

| # | unit | done when |
|---|---|---|
| 0.1 | merge `investigator/row-3-citations` (nine commits: row 6, the readable transform, the validator applying a model's patch, M7 rows 3–4, row 3) | merged after the local gate and the full guard pass are green on the Mac |
| 0.4 | CI demoted (decision CI): `.github/workflows/ci.yml` runs on `workflow_dispatch` only, so it spends nothing unless someone asks; `agent_briefing.md` (then `sync_briefing.py`), `review_playbook.md`, `CLAUDE.md`'s own sections and the README say the local gate and the artefact qualification replace "CI green on Windows and macOS" | the briefing test green; no document still names CI as a merge gate |
| 0.2 | `python -m adii.reporting.manifest` then `--verify`; commit `01_data/runs/MANIFEST.json` | verification prints OK with nothing unlisted |
| 0.3 | the baseline written into the log at the end of this file: test count, guard count, archived runs, source revision | the log's first row is filled |

Gate: `python -m pytest` and `python 02_src/scripts/guard_check.py` on `main`.

---

## Phase 1 — Close the benchmark-critical seams

Each seam can invalidate the final evidence; that is why they come before any run that
will be shown.

### 1.1 The judge on the scoring path (decision J)

**Problem.** A model does not reproduce a key's exact `repair_id` or `root_cause_id`, so
every correct, accepted REPAIR routes to the judge; with none wired the report says
`failure / unresolved`. The benchmark would measure the harness, not the investigator.

**Unit.** A standard-library judge in `02_src/adii/provider/judge.py`: one request through
`worker.transact`, the credential from the environment or `.env.local`, a priced model,
temperature 0, `max_tokens` bounded, usage returned. `python -m adii.evaluation` gains
`--judge-model ID`; when a case routes to the judge and no model is given, the report says
`unresolved` exactly as today; when given, `judge_repair` runs and the report carries
`judge: {model, prompt_sha256, verdict, reasoning, usage, cost_usd, price_table}`.
`evaluation/openai_provider.py` and the `judge` extra are deleted; `openai` leaves
`pyproject.toml`, `requirements.txt` and the suite's chosen-dependency set. Net delta
negative.

**Acceptance.** An archived REPAIR run whose ids differ from the key scores `success`
settled by the judge when a model is given and `failure / unresolved` when not; the
judge's prompt digest and verdict are in the report; the credential is in no artefact
(the existing grep test extended to the report). Guards:
`C.judge_unresolved_without_a_judge`, `C.judge_verdict_recorded_by_digest`.

**Freeze input.** The judge model and the prompt digest are frozen with the scorer in
phase 4.

### 1.2 The grounding check reads the trace as it is

**Problem.** `check_grounding` looks for `call["tool"]`; the trace records `name`. On a real
trace it raises.

**Unit.** `evaluation/grounding.py` reads the trace's `tool_call` payload shape, and returns,
per predicate, whether it was observed and the `evidence_id` of the matching successful
result. `python -m adii.evaluation` gains `--grounding-key PATH` (hash-bound to the answer
key, as `grounding.py` already requires). The report's `grounding` gains
`decisive: {observed, cited, missing}` beside the existing `grounded` — additive.

**Acceptance.** Driven by an archived record's trace, not a fixture shaped by hand; D5b's
shape reproduced: disposition `success`, `decisive.observed` false, both present, neither
folded into the other. Guard: `C.decisive_is_read_from_the_trace`.

### 1.3 Row 1 — the record holds what the model was sent (decision R1)

**Problem.** `model_requested` carries a count of messages. The receipt binds the protocol
by digest, so the instruction is provable today; it is not readable from the record.

**Unit.** `model_requested` gains `sent`: the messages appended since the previous request
(turn 1: the system message and the incident document; later turns: the observation or
rejection message). The count stays for archived records. The page's turn card shows the
turn's message under its raw events; the text report is unchanged.

**Acceptance.** Against the fake endpoint, the messages it received on every turn equal the
reconstruction from the trace; the receipt's protocol digest equals the digest of turn 1's
system message. Guard: `D.request_records_what_was_sent`. Row 1 marked in the trace
contract's decision record in its own commit.

### 1.4 Row 5 — no stop without a decision on the live path (decision R5)

**Problem, and a hazard the docs do not name.** The loop's rejection message names three
forms, `<STOP>` among them; the protocol advertises two. A model that was just rejected is
told `<STOP>` is legal and can end the run with no decision, which lands as a placeholder
`model_failure`.

**Unit, recommended.** `<STOP>` leaves the live grammar: the constant, the `loop_stopped`
event and the `decision is None` branch in `runtime/live.py` are removed; the scripted
tests that ended with a stop end with a decision or a bound; the rejection message and the
protocol name the same two forms. Row 5 resolves as: there is no stop without a decision
on any path. Net delta negative.

**Alternative, if the architect prefers to keep the form.** A named termination class
added to the closed set in `reporting/record.py`, with the renderers, the phrasing
dictionary and `not_evaluable` following. Half a day either way.

**Acceptance.** A model replying `<STOP>` is recorded as an invalid envelope and told once;
`grep -r "row 5"` finds no placeholder in `02_src/adii`. Guard:
`A.stop_is_not_a_form` (recommended path). Row 5 marked in its own commit.

### 1.5 The validator beyond one world — configuration A (decision V)

**Problem.** Only the teaching incident is rebuildable; every other REPAIR ends
NOT_CHECKABLE. D1 and D3 need configuration A to reach ACCEPT and REJECT, and the live
demo needs one rebuildable world that is not the walkthrough.

**Unit.** A generic rebuild in `validation/patching.py`: the incident package's `world.sql`
builds the base tables; its transform bundle declares the pipeline in order; the patch
replaces exactly one declared transform; the rebuild runs the pipeline in a fresh
in-memory database under the build budget. Checks in `validation/checks.py` become
generic where they can — the rebuild itself, and row identity preserved on every table the
patched transform does not derive — and per-incident where they must: one oracle
declaration per rebuildable incident in `02_src/adii/validation/oracles/<id>.json`, a pair
of queries that must agree (an independent recomputation over base tables against the
rebuilt mart). The oracle lives with the validator, keyed by incident id, never under
`01_data/`, and states an invariant the repaired world must satisfy, not the patch. The
registry `_WORLD_BUILDERS` becomes the set of incidents that carry an oracle.

**Acceptance.** D3's four outcomes through the real runtime on configuration A: the
correct patch ACCEPT; a symptom-removing wrong patch REJECT by the oracle; an out-of-path
patch DENIED by authorization and still validated; an inapplicable patch REJECT by
`rebuild`. The walkthrough keeps passing through the same generic path. Guards:
`C.oracle_is_declared_per_incident`, `C.untargeted_tables_keep_identity`.

**Order rule (decision V).** The mechanism lands in phase 1, proved on the walkthrough
through the generic path and on test-only packages written under the test's temporary
directory. Configuration A's package, and its oracle, enter in phase 2 after the reserve
commitment (2.2), so no evaluated case exists before its authority sequence allows it.

**Scope rule.** Configuration A first, because D1 and D3 require it. `delivery-duplicated`
second if phase 1 has time left, because identity-against-count is the best D3 story. No
third world in this plan.

**Deferred, by decision R4.** Per-event timestamps and latency derived from the trace.
Latency stays a wall clock around the run, and the evaluation report says so.

Gate: everything in phase 0's gate, plus `python -m adii.runtime --incident demo-learning-001
--provider local ...` against the local model ending in a REPAIR with a computed verdict,
citations resolved, the sent messages in the record.

---

## Phase 2 — The development set

**Revised 23 September.** The bootcamp brief asks for a clear end-to-end agent over
reasonable data — synthetic data is named as acceptable — and for labelled eval data, which
the team may annotate itself. So the private-corpus compilation, the reserve commitment and
the catalogue's seven decision rows are not needed and are not done; the set is generated
here, and the team labels it.

**Built.** `python -m adii.examples.canonical_world` writes 18 incident packages under
`01_data/incidents/`: six families — six companies, each with its own day, volume,
distributors and decoy release — and in each the same alert over three states of the
evidence: the load stopped part-way (REPAIR), the business really changed (NO_REPAIR), the
evidence cannot decide (ESCALATE). Half the families are explicit, their notices saying what
happened; half are implicit, the evidence only in the data. Ids are opaque; the generator
writes worlds, never answers. Labels, authored by the team and frozen by digest before any
run: an answer key and a grounding key per case under `02_src/adii/evaluation/catalogue/`;
an oracle per case beside the validator.

**Gate.** `tests/integration/test_incident_packages_are_ready.py`: every package is its
generator's output, states no answer, shares every surface with its siblings, is reachable
through the real tool layer, and is rebuildable; every case has a frozen key and a bound
grounding key; and every case is solvable — an ideal scripted investigator makes the
decisive calls, cites them, and scores success with the decisive evidence observed and
cited, a REPAIR accepted by the validator and admissible. The six specimens stay for the
page's history and are not in the benchmark.

---

## Phase 3 — Controls and measurement

**Goal.** The three arms, every repeat materialised, the semantics pre-registered, and a
report that reads records only.

### 3.1 The arms

`--arm full | alert-only | always-escalate` on `python -m adii.runtime`, in the receipt's
configuration and reason. `alert-only`: the same protocol with no tool advertised, every
call DENIED as unknown. `always-escalate`: no model; a deterministic investigator submitting
ESCALATE with a fixed summary and no citation. The evidence-gate policy for `alert-only`
(decision G): run both variants once, `evidence_gate: kept` and `relaxed_for_arm`, each in
the configuration, as DECISIVE_TESTS recommends.

### 3.2 The grid runner (D-17)

`python -m adii.evaluation.grid --pack <name> --catalogue … --arms … --repeats 3 --provider
local|openai --model …`: every cell through the runtime's own entry point, labels
`<incident>-<arm>-r<k>-<pack>`, one run at a time, a per-run cap and a pack cap stated in a
pack receipt written first; a cell that fails is an archived record, never a missing cell;
then every run scored with its key and grounding key. The repeat rule (decision R): two of
three per cell; a disagreement between repeats is listed, never averaged.

### 3.3 Semantics v2, pre-registered (decision S)

A new frozen file, `scoring_semantics_v2.json`, ratified before the paid pack: the six
categories unchanged; `unsafe_certainty` as a sub-kind when the key says ESCALATE and the
decision is REPAIR or NO_REPAIR; the grounding dimension defined (`grounded`,
`decisive.observed`, `decisive.cited`) and never folded into the category; the judge rules
carried from v1. `test_scoring_semantics` pins v2 the way it pins v1.

### 3.4 The benchmark report

`python -m adii.evaluation.report --pack <name>` reads records and evaluation reports only
and writes `benchmark_report.json` and a markdown table: per arm, incident and repeat the
category, sub-kind, grounding, validation state, authorization, cost lower bound and
latency; denominators; repeat disagreements; and D1–D5 read against DECISIVE_TESTS as
written, pass or fail.

**Acceptance for the phase.** The whole pack runs against the fake endpoint in a test with
every cell materialised, and once for real on the local model.

---

## Phase 4 — Freeze A, the evaluation freeze

Two freezes, because one commit cannot hold results that do not exist yet (decision F):
**Freeze A** binds what the benchmark evaluates, before it runs; **Freeze B** (7.5) binds
what is submitted, after the evidence exists. Feature development ends at Freeze A; from
then on the work is measure it, prove it, communicate it.

`python -m adii.evaluation.lock --name freeze-<date>` writes
`02_src/adii/evaluation/freezes/<name>.json`: the sha256 of every file the evaluated system is
made of — every module under `02_src/adii` (the runtime, the provider adapter and its
reasoning-model settings, the protocol, the tools, the validator and its oracles, the scorer
and its semantics, the judge's prompt, the price table, the record schemas, the front door
and its backend), the pinned requirements, the incident packages and the catalogue (keys,
grounding keys, the partition with its superseded list, the burned list) — the terms of the
four registered final packs written out in full (decision E: model, effort, bounds, arms,
incidents, caps), and the commit it was taken at. Prices are verified against the provider's
page first (done 23 Sep). The freeze file is committed with the tree it digests and the
merged commit tagged `freeze-<date>`. From then on `test_the_freeze.py` fails the gate if any
frozen file changes, and the grid refuses a registered pack unless the tree matches the
newest freeze with its frozen terms; each pack's receipt names the freeze by digest.
Nothing frozen changes because of a result.

**Qualification of the frozen commit, on clean macOS and Windows.** `python
02_src/scripts/package_submission.py --ref freeze-<date>` builds `adii_submission.zip` from
the tag (standard library only; `SUBMISSION.json` lists every file by sha256; the same
inputs build the same bytes; it refuses a `.env` file or the configured key's prefix in any
file). Extracted on each machine, from nothing: `py -3.12 -m venv .venv` (`python3.12` on
the Mac), `pip install -r requirements.txt`, `python 02_src/scripts/check_env.py`, `pytest`,
`python -m adii.runtime --incident demo-learning-001 --provider scripted`, `python -m
adii.demo`, and the launch view in a browser. A failure is fixed and Freeze A is taken again
under a new name, before any pack runs.

**Rule.** Any engineering change after Freeze A is a new freeze version. A pack scored under
one version is never re-read under another
([inherited/AUTHORITY_LIFECYCLE.md](inherited/AUTHORITY_LIFECYCLE.md)).

---

## Phase 5 — The benchmark, once

| # | unit | done when |
|---|---|---|
| 5.1 | the paid rehearsals: `pilot-paid-v1` (gpt-4.1), `pilot-paid-v2` (gpt-6-sol), `pilot-paid-v3` (gpt-6-luna, on the burned cases) | done; machinery only; excluded from every result |
| 5.2 | the pre-flight the morning of the packs, one per model: `python -m adii.provider --check --spend --model <m> --max-tokens 4096` with `--reasoning-effort low` for gpt-6-sol and gpt-6-luna | `spend_check: PASS` and `reserve_premise: holds` for each |
| 5.3 | the four registered packs, once, on Freeze A (decision E): `final-sol` (benchmark: full, alert-only, always-escalate), `final-luna` and `final-gpt-4-1` (benchmark, full), `final-held-out` (held-out, full, gpt-6-sol) — 54 paid runs and the free floor; the effort for the reasoning models and temperature 0 for gpt-4.1 as frozen | every cell archived and scored; nothing re-run, nothing tuned; `python -m adii.reporting.manifest` attests the archive; a second copy of the run folders kept off this machine |
| 5.4 | the packs read against DECISIVE_TESTS as written | D1–D5 each pass or fail, recorded in a new section of release_evidence.md — appended, never rewritten |

Three claims, reported apart and never blended: the architecture across three investigators
(same 12 incidents); whether the tools add information beyond the alert (Sol full against
Sol alert-only, with always-escalate as the free floor at 4 of 12); and the declared system
on six cases nobody tuned on — a demonstration, not a statistic.

---

## Phase 6 — The evaluation report

| # | unit | done when |
|---|---|---|
| 6.1 | `02_src/docs/evaluation_report.md`, generated from the packs' `report.json` by a script under `02_src/scripts` (outside Freeze A: it reads records, it is not the evaluated system): protocol, partition, the three claims, per-truth and per-tier results, grounding, validation, the admitted-where-no-repair-was-right count, cost, latency, the failures by name, limitations; the claim boundary updated in release_evidence.md by a new section | every number traces to a run label |
| 6.2 | the product page does not show benchmark results (decision R): results are evaluation material, and a frozen product is not modified to display what it produced | — |
| 6.3 | the demo configuration is the final packs': `python -m adii.demo 8000 --provider openai --model gpt-6-sol --reasoning-effort low --max-tokens 4096 --max-cost-usd 0.50 --max-turns 20` | the receipts of the filmed and live runs carry the same bounds as the packs' |

---

## Phase 7 — Presentation, film, submission

### 7.1 The deck, ten minutes

```text
0:00–1:00  PROBLEM AND CATEGORY   "The number moved. Should anything change?"
                                  Observability tells you something changed;
                                  ADII determines whether intervention is justified.
                                  We call this governed agentic investigation.
1:00–2:00  HOOK                   a model's proposal is not the system's acceptance
2:00–3:00  MECHANISM              one door to the world; grounding, authorization, validation
3:00–6:00  PRODUCT, LIVE          the visitor's CSV → incident → investigation → answer
6:00–7:15  ADMISSIBILITY          the square: works but not allowed · allowed but does not work
7:15–8:15  EVIDENCE               the controlled benchmark; the receipt, the bounds, the record
8:15–9:00  CLAIM BOUNDARY         what has been proved, what has not, in its own words
9:00–10:00 CATEGORY, MARKET, ASK  design partners · platform partners · capital
```

Three proof objects and no more on stage: the admissibility square, the benchmark, the
receipt. Guards, tests, operating systems and dependencies are one credibility slide, and
the appendix for the partner room.

The ask, in three tiers: **design partners** bring the structure of the incidents their
teams face, the evidence that was available and what would have counted as a justified
intervention — never their data; **platform partners** connect ADII to their model and
runtime; **capital** funds the move from one executable proving domain to several governed
operational domains.

The hierarchy, said once: product today, ADII; use case, operational incident
investigation; category, governed agentic investigation; platform thesis, admission
control for consequential agent decisions.

### 7.2 The partner session

The first half as above. The second half answers four questions — why a model provider
cannot solve this inside the model, why now, why ADII, why this team — then shows the
falsification condition from release_evidence.md §7 and ends with the design-partner ask.
The technical appendix carries the boundary tests, the guard pass, the freeze digests and
the benchmark report.

### 7.3 The live script

From the launch view (`#new`), which shows no earlier answer. The live case is a version-2
sample of the demo company — LEAVE, the restraint the room does not expect; the FIX is
precomputed on the frozen build and opened straight after it to show proposal,
authorization, independent rebuild and sign-off; ESCALATE is held for questions. Never an
audience upload. One person speaks, one drives. The spoken line for any ending, including a
failure: the sentence on screen came from the record, not from us. A hung run is rehearsed:
it ends at its bound, and the page says so.

### 7.4 The film, from Freeze A

From the frozen build only: the finished interface, one version-2 FIX case run from the page
with its label on screen, the before chart and the independent rebuild, the sign-off, the
final numbers from the report; the last line "if it is not in the trace, it did not happen".
The version-1 FIX kept from the integration gate is not filmed beside a revenue figure: its
alert predates decision A2.

### 7.5 Freeze B, the submission freeze — against the exact ZIP

The artefact the bootcamp receives is what is qualified, never a developer checkout. Freeze
B adds, after the evidence exists: the evaluation report, the refreshed README (architecture,
how to run, the evaluation's method and results, the deployment limits stated plainly), the
architecture diagram drawn from the frozen architecture, the screenshots, the film and the
presentation material. Nothing under Freeze A changes; `test_the_freeze.py` proves it.

1. The merged commit tagged `submission-<date>`; `python 02_src/scripts/package_submission.py
   --ref submission-<date> --packs final-sol final-luna final-gpt-4-1 final-held-out`; its
   `SUBMISSION.json` reviewed by the architect: the three top-level folders, the README, the
   requirements, the packs' receipts, reports and run folders the report cites.
2. No secret: the packager refuses a `.env` file and the configured key's prefix anywhere;
   checked by hand as well.
3. Extracted on a clean Mac and a clean Windows machine; on each, from nothing: the
   environment, the requirements, `check_env.py` prints `Ready.`, `pytest` green, the
   scripted runtime archives a run, `python -m adii.demo` serves and the launch view and one
   archived answer work in a browser.
4. If anything changes after this, the ZIP is rebuilt and step 3 repeated on both machines.
   The ZIP that was qualified is the ZIP that is uploaded, by digest.

### 7.6 Rehearsals

Three full run-throughs on the frozen build, one on the venue network or a hotspot, the
pre-flight the morning of D and again the morning of P.

---

## What sets the pace

Not the code. These, in order:

1. **The decisions.** Every unit waits on its row in the table below and on nothing else.
   Marking them early is the single largest acceleration available.
2. **The freeze order.** Keys before runs, the freeze before the paid pack, the paid pack
   before the report, the report before the film. None of these can overlap.
3. **The paid pack, once.** A defect found after it means a new freeze and a new pack,
   paid again. The local pack in 5.1 exists so that does not happen.
4. **Windows qualification.** It needs a Windows machine and a person at it, twice at
   most: on the frozen build, and on the final ZIP if anything changed.
5. **The calendar.** The film is shot at D−3 from the frozen build; the rehearsals need the
   presenters.

Never cut: the judge, the grounding fix, row 1, the freeze, the paid pack run once, the
film from the frozen build, the qualification of the exact ZIP. If the calendar forces a
scope cut, the order is: the second rebuildable world, the benchmark view on the page
(the markdown table is shown instead), the `relaxed_for_arm` variant of alert-only.

## What this plan does not do

- No unseen or blind evaluation: `UNSEEN-EVALUATED` stays HOLD. The reserve commitment
  (2.2) keeps it possible after the capstone.
- No second domain adapter, no connector, no permission model, no customer.
- No repair is ever executed. Admission is derived, and nothing writes.
- No new dependency. The one the plan touches is removed.

## Decisions the architect marks before the unit that needs them

| # | decision | recommended | mark | commit |
|---|---|---|---|---|
| CI | CI demoted to manual dispatch; the local gate on the Mac is the merge gate; cross-platform correctness by qualifying the exact ZIP on Windows and Mac | APPROVED | APPROVED — the project owner, 23 Sep 2026 | phase 0 |
| J | the judge: a standard-library provider, its prompt and verdict in the report, frozen with the scorer; the SDK provider and the `openai` extra deleted | APPROVED | APPROVED — the project owner, 23 Sep 2026: the judge frozen (model, prompt digest, verdict, usage, cost recorded), and the settlement source explicit in every report — deterministic, judge or unresolved | decisions |
| R1 | trace contract row 1: `sent` on `model_requested` — the messages added since the previous request; the count kept | APPROVED | APPROVED — the project owner, 23 Sep 2026 | decisions |
| R5 | trace contract row 5: `<STOP>` leaves the live grammar; no stop without a decision on any path | APPROVED, removal | APPROVED, removal — the project owner, 23 Sep 2026 | decisions |
| R4 | trace contract row 4: per-event timestamps | DEFER — latency stays the wall clock, said so | | |
| R7 | trace contract row 7: an event for the authorization fact | DEFER — the record carries it; nothing reads an event | | |
| V | the validator generalised as in 1.5; oracles live with the validator, keyed by incident, never under `01_data/` | APPROVED | APPROVED — the project owner, 23 Sep 2026, with an order: the mechanism is generalised first and proved on the walkthrough and on test-only packages; configuration A enters as a catalogue package in phase 2, after the reserve commitment, never before | decisions |
| C1–C7 | the catalogue rows | not needed | DEFER — not needed: the set is generated and team-labelled, as the bootcamp brief allows (23 Sep) | |
| G | alert-only's evidence-gate policy | both variants once, each in the receipt | | |
| R | the repeat rule | two of three per cell; disagreements listed | | |
| S | semantics v2 as in 3.3 | APPROVED, frozen before the paid pack | | |
| P | a paid rehearsal before the freeze: `pilot-paid-v1`, 20 runs on the final model and terms, excluded from results; it may change machinery (response handling, a bound too small mechanically, serialisation, arm wiring, price or cap accounting), never success criteria — no key, prompt or incident changed because the model decided a case wrongly | APPROVED | APPROVED — the project owner, 23 Sep 2026: the local model cannot rehearse on this machine, and a protocol defect found inside the counted pack would cost the pack | 5.1 |
| M | the paid pack's model and bounds; the judge's model | gpt-4.1, twenty turns, $0.50 per run; judge gpt-4.1-mini at temperature 0 | | |
| M2 | decision M amended, before any result on the final model: gpt-6-sol (released 22 Sep 2026, OpenAI's model for agentic work, $2/$10 per million), chosen ex ante — no bake-off on the development incidents, which would select the model on the test; reasoning effort `low`, sent in place of `temperature`; a 4,096-token completion bound as `max_completion_tokens`, reasoning inside it; five repeats — 18 × 2 × 5 = 180 paid runs, a worst case of 180 × ($0.50 + $0.01) = $91.80, a fail-closed reserve and not a forecast; `pilot-paid-v2`, the same 20 cells on Sol, machinery only; the gpt-4.1 pilot is set aside | APPROVED | APPROVED — the project owner, 23 Sep 2026 | 5.1 |
| B | burn the six load-stopped cases and replace them with six transform-defect cases, before the freeze. The load stopped part-way; the permitted transform stages up to the loader's acknowledged line by design (DATA-88); so the operational repair is a replay the permitted path cannot make, and the REPAIR label asked a model to rewrite what the world calls intentional — established from the world alone, the rehearsals only what drew attention to it. The burned packages, keys and rehearsal records stay as they are (`catalogue/burned.json`); the default pack leaves them out. The replacements are written under the REPAIR validity rule: **a case is labelled REPAIR only when the permitted change surface is itself the cause of the observed error, a change entirely within that surface restores the world's truth, and the validator tells that repair from a cosmetic and from a no-op alternative.** In each, every order arrives and loads, and that morning's staging change DATA-97, meant for sandbox test orders, names live distributors from the day. Keys authored and frozen from the generator before any model saw the worlds; qualified deterministically — the restored transform ACCEPT and admissible, the chart-only fake and the defect resubmitted REJECT, on all six; no model run on them before the final pack | APPROVED | APPROVED — the project owner, 23 Sep 2026 | phase 4 |
| E | the final evaluation, registered before the freeze, replacing M2's five repeats: breadth and separated evidence over repetition. `catalogue/partition.json` — **benchmark**, 12 cases, the mar, may, oct and dec companies, two per truth and tier; **held-out**, 6 cases, every live case of jul (explicit) and sep (implicit), the two companies no pack had run — one per truth and tier, never run before the final pack (a test holds every committed pack receipt to it); **demo**, the three live cases of a seventh company, aug, generated for the stage and run in no pack. Held-out, not blind: the team wrote these keys and the generator is in the repository; what is held is that no model has run them and nothing was tuned on them. Four packs, one repeat, the same protocol and bounds (twenty turns, a 4,096-token completion bound, $0.50 a run, judge gpt-4.1-mini): `final-sol` — gpt-6-sol at effort low on the benchmark, full, alert-only and always-escalate (24 paid); `final-luna` — gpt-6-luna at effort low, full (12); `final-gpt-4-1` — gpt-4.1 at temperature 0, full (12); `final-held-out` — gpt-6-sol, the declared production investigator, full, on the held-out six (6). 54 paid runs, a worst case of 54 × $0.51 = $27.54. Three claims, reported apart: the architecture across three investigators; whether tools add information beyond the alert; the declared system on cases nobody tuned on — six cases, a demonstration and not a statistic. Luna, not rehearsed, is qualified on the burned cases first (`pilot-paid-v3`), which no result reports | APPROVED | APPROVED — the project owner, 23 Sep 2026 | phase 5 |
| F1 | the front door's chart is the record's: a package may declare its alerted series (`alert_series.json`: metric, unit, query — beside the world, never shown to the model); the runtime reads it through the read-only database once, before the investigation, and records it as `alert_observed` — a new trace kind, never a tool call, so never the model's evidence or grounding. Every canonical package declares daily revenue from the mart | APPROVED | APPROVED — the project owner, 23 Sep 2026 | the front door |
| F2 | "after validation" is the validator's reading: `ValidationResult.rebuilt_series`, the declared series read from the rebuilt world with the same query, on ACCEPT and REJECT alike, empty when nothing was rebuilt; a contract row, and the record moves to `adii.run_record/v3` (v2 and v1 still load) | APPROVED | APPROVED — the project owner, 23 Sep 2026 | the front door |
| F3 | "How ADII knows" is built from the investigator's citations: each cited observation rendered by a fixed template from its recorded result — no model wording, no protocol change | APPROVED | APPROVED — the project owner, 23 Sep 2026 | the front door |
| W | the product's name beside the unchanged logo: **ADII — Is it broken?** The question before the machinery; Fix it · Leave it · Escalate it are the answers, and maker-checker is the reveal. The category line, once understood, elsewhere: "Intervention assurance for consequential data changes." | APPROVED | APPROVED — the project owner, 23 Sep 2026 | the front door |
| A2 | the alert names the number it measured: version 1 said "revenue fell about N%" where N was the orders' fall; the orders fall by the same share in every state of a family and the revenue does not (mar: 48% and 44%), so a shared alert can only state the orders. Version 2 of every live case — "Daily revenue for D fell sharply: the day counted about N% fewer orders than a usual day." — under new ids, the same worlds and answers, keys copied and frozen anew, the partition moved to them; version 1 kept byte for byte and listed as superseded, since the rehearsals, the integration gate and the stage's precomputed FIX ran on it and no record is rewritten. The chart states the revenue's fall under its own name. Before any final run and before the freeze | APPROVED | APPROVED — the project owner, 23 Sep 2026 | phase 4 |
| F | two freezes: Freeze A binds the evaluated system before the benchmark runs; Freeze B binds the submission after the evidence exists; feature development ends at Freeze A | APPROVED | APPROVED — the project owner, 24 Sep 2026 | phases 4 and 7 |
| R | no benchmark result on the product page: the front door shows alert, investigation, answer, evidence, proposal, sign-off and record; results live in the report and the deck | APPROVED | APPROVED — the project owner, 24 Sep 2026 | phase 6 |
| CL | the claim: "ADII is a complete, locally running reference implementation. We engineered and qualified the authority boundaries as if they mattered in production; we have not deployed it into a production customer environment." — industry-grade engineering discipline, never "production-grade deployment" (no HA, SSO, secret management, connectors, operations, residency or workload history is claimed) | APPROVED | APPROVED — the project owner, 24 Sep 2026 | phase 7 |

## The audit of 23 Sep, before the freeze

An outside conformance audit of `8a653d7` against the inherited A–D requirements. Each
finding, what was done, and what the benchmark may therefore claim.

| # | finding | resolution |
|---|---|---|
| D3 | the live `trace.jsonl` wrote with `default=str` and allowed NaN | FIXED — strict: `allow_nan=False`, no fallback; a payload that is not JSON is refused before a byte is written |
| D4 | `evidence_refs`, validation `reason_code` and `authorization` joined the record under `adii.run_record/v1` | FIXED — new records are `adii.run_record/v2` and must carry all three; v1 still loads as it declares itself; the page renders both |
| D5 | a run the grid could not score was filed under its termination (`submitted`) | FIXED — it is `unscored` in the report and named under "Runs not scored". An exception escaping the runtime still stops the pack: the runtime archives all four endings, so an escape is our defect, loud, and the pack resumes past every archived cell |
| labels | `false_repairs_admitted` counts only admitted repairs where the key says no repair; `tool_calls` counts executed calls | FIXED, the name — `admitted_where_no_repair_was_right`; a wrong repair admitted on a REPAIR incident is in the categories. `tool_calls` is reported as executed calls, never attempts |
| boundary | the investigator's file-I/O test caught `open()` only | FIXED — the investigator and contracts may not import `pathlib`, `os`, `io`, `shutil`, `glob` or `tempfile` |
| A2 | the loop does not validate arguments against an advertised schema independently of the executor | DEFER — one executor exists, and it rejects wrong types as `REJECTED`; the claim is made for that executor only |
| A3, A4, D9 | no property tests of schema forms; no independent context ceiling | DEFER — a run is bounded by twenty turns, 1,024 completion tokens a request and a $0.50 hard cap reserved before each request; no context-size claim is made |
| C, provenance | the oracles' invariants carry no record of an operational authority independent of the benchmark | STATED, not fixed — they are the data contract of a world the team generated, written with it. The claim: the validator knows invariants and never answers, and checks a repair against the world's own contract. Never: an independent authority certified them |
| C, reasons | a matching NO_REPAIR or ESCALATE is scored on disposition; the reason is not adjudicated | STATED — reported as disposition-correct, with grounding (was the decisive evidence observed and cited) beside it; never called reason-aware |
| admissible | authorized and ACCEPT, with no semantic-support term | STATED — admissible means the target was permitted and the rebuild held the invariants; evidentiary support is the grounding column, evaluator-side; nothing executes |
| D13 | the pilot's files are not in the attested manifest | at the freeze: the manifest is rewritten over the whole archive, the pilot included and labelled excluded; the second copy is 5.3's `--preserve` |
| X2, X4 | no install test at each dependency floor; CI not automatic | DEFER X2 — the ZIP is qualified on clean Windows and macOS (7.5); X4 superseded by decision CI |

## Log

| date | phase | what closed | revision |
|---|---|---|---|
| 23 Sep 2026 | 0 | 0.1 already done: the nine-commit branch reached `main` as PR #39 on 22 Sep, content-identical. 0.2: the archive attested, 138 artefacts across 49 run folders, verified OK. 0.3 baseline on the Mac: ruff clean; 1,190 tests passed, 13 skipped (the blind-key tests, kept out on purpose); 137 of 137 guards killed. 0.4: decision CI marked; the workflow runs on dispatch only; the briefing, CLAUDE.md, AGENTS.md, the review playbook, the build plan's done-when and the adii-change skill state the local gate and the ZIP qualification | `main` at 3914d23 |
| 23 Sep 2026 | 1.2 | the grounding check reads the archived trace: a predicate is observed only when its call was answered OK; `decisive: {observed, cited, missing}` beside `grounded` in the report via `--grounding-key`, the key refused unless bound to the answer key given; the invented trace shape and its tests replaced by the walkthrough record's real trace; D5b reproduced end to end; guards `C.decisive_is_read_from_the_trace` and `C.grounding_key_bound_to_this_answer_key`, both killed | branch `evaluation/grounding-reads-the-trace` |
| 23 Sep 2026 | decisions | J, R1, R5 and V approved by the project owner; trace contract rows 1 (in part) and 5 marked | |
| 23 Sep 2026 | 1.4 | `<STOP>` left the grammar: the loop returns a decision or raises, the live adapter's placeholder `model_failure` is gone, the rejection message names two forms; a `<STOP>` reply is an invalid envelope, told once; scripted tests end in an ESCALATE decision; the live path's model failure is exercised by a reply in the API's shape with no text; the plan's `A.stop_is_not_a_form` guard is not registered, because removed code leaves nothing to neutralise — the rejection path it rides on is already guarded; A 7 of 7 and D 78 of 78 killed; 1,196 passed | |
| 23 Sep 2026 | 1.3 | trace contract row 1 built: every `model_requested` carries `sent`, each message appended since the previous request — the protocol and the incident first, then the model's own reply and what answered it — so any turn's whole prompt is the `sent` lists joined, held equal to what the endpoint received turn by turn, and the receipt's protocol digest held equal to the system message actually sent; `messages`, the count, kept; the page shows `sent` in each turn's raw events and adds no sentence; guard `D.request_records_what_was_sent`, killed | |
| 23 Sep 2026 | 1.1 | the judge on the scoring path: `provider/judge.py`, standard library, one request per routed case through the run's own transaction, a priced model at temperature 0 with a bounded reply, the credential from the environment or `.env.local`; `python -m adii.evaluation --judge-model ID [--judge-endpoint URL]`; the report keeps `settled_by` (deterministic, judge or none) and, when the judge settled it, `judge: {model, prompt_sha256, usage, cost_usd, price_table, verdict, justification}`; without a judge the case stays `failure / unresolved`; a reply that is not a verdict scores nothing; the SDK provider, the `judge` extra and the `openai` pin deleted — zero third-party runtime dependencies, and three chosen development tools; guards `C.judge_unresolved_without_a_judge` and `D.judge_named_by_prompt_digest`, both killed | |
| 23 Sep 2026 | 1.5 | the validator is a mechanism: a rebuild runs the incident's own pipeline from its frozen world and transform bundle, a patch may replace only a transform the pipeline declares, and one check compares invariants row for row; each rebuildable incident has an oracle beside the validator — pipeline and invariants, a closed shape that refuses a patch, a repair id or a disposition; the walkthrough runs on it, and D3's four outcomes are proved through the real runtime on a test-only package shaped like configuration A — correct: authorized, ACCEPT, admissible; symptom-hiding: REJECT by the oracle; correct but outside the path: DENIED and ACCEPT; inapplicable: REJECT by rebuild; the plan's untargeted-identity check is not built, because a rebuild re-derives only pipeline tables from the frozen world, so base tables cannot change by construction; the report's judge field renamed `justification`; guards `C.oracle_shape_is_closed` and `C.invariants_compare_rows` added and four validation rows moved with the code, all killed; phase 1 closed | |
| 23 Sep 2026 | 2 (data) | the data audit found the specimens cannot carry the benchmark — no derivable pipelines, missing evidence, empty permitted paths leaking ESCALATE — so the canonical world was built first: `python -m adii.examples.canonical_world` writes one alert, one schema, one tool surface, one permitted path and one decoy release into three packages under `01_data/incidents/` with opaque ids, differing only in what the evidence says (the load stopped at 55 of 100; two distributor contracts ended; the manifest claims 100 under a known counting fault and the vendor receipt is missing); the generator writes worlds and never answers; three oracles authored beside the validator; the data-readiness gate holds every package to its generator, to no stated answer, to one surface per alert, to reachability through the real tool layer and to a pipeline that reproduces its own world; the stage story held on the real packages — scale-to-the-total recovers the chart and is rejected, the load repaired is accepted, a repair of a world that was never broken is rejected by a new generic check that a repair changes the world; `--incident <id>` and the page resolve packages; guards `C.a_repair_changes_the_world` and `D.incident_id_is_one_segment`, both killed; the specimens stay for the page's history and are not in the benchmark; keys and grounding keys next, frozen before any run | |
| 23 Sep 2026 | 2 | the set scaled and labelled: six families × three states = 18 generated packages, explicit and implicit tiers, 18 answer keys and 18 grounding keys frozen, 18 oracles; the gate proves every case solvable and its labels consistent; the reserve commitment and catalogue rows dropped as unneeded for the brief | |
| 23 Sep 2026 | 2 (scale) | capacity measured apart from decision quality: `python -m adii.evaluation.scale` grows the canonical world's exact incidents and holds the decisions. Probing it found three defects that only scale shows, all fixed: the validator falsely rejected a correct repair at 1M orders because its rebuild budget was a fixed instruction count — it now scales with the frozen world's own build; the decisive per-day query was refused at 5M because the query budget was fixed — it now scales with the rows the world holds, a cross join still cut; invariant checks held both sides' rows under a 100,000-row cap — they now compare streamed multiset fingerprints. On this machine (M4, 16 GB): 10k, 100k, 1M and 5M orders all reach the same three decisions, the correct repair ACCEPT and the fake REJECT at every size; validation 0.06 s, 0.7 s, 6.2 s and 33 s; peak memory 50 MB, 0.3 GB, 2.7 GB and 6.7 GB, so in-memory worlds end near 5M orders on 16 GB; the orders extract indexed by day; guards `B.query_budget_scales_with_the_world` and `C.rebuild_budget_scales_with_the_world`, both killed | |
| 23 Sep 2026 | 3 | the controls built: `--arm full | alert-only | always-escalate` on the runtime — alert-only the same model and protocol with no tool registered, so every call is refused as unknown; always-escalate no model at all, with `--provider none`, each requiring the other — the arm in every configuration and receipt; `python -m adii.evaluation.grid` runs every labelled incident × arm × repeat through the runtime's own entry point, resumes without re-running a cell, refuses a resumed pack with other terms, refuses a paid pack whose worst case (every paid run spending its whole cap) crosses `--pack-cap-usd` before anything runs, scores each run against its frozen key and grounding key, and writes the report from the records alone — per arm right, by truth and by tier, decisive evidence seen, false repairs admitted, cost; the evidence-gate policy for alert-only is left as it is, one variant, said as such; guards `D.floor_arm_asks_no_model`, `D.alert_only_sees_no_tool`, `C.pack_worst_case_within_its_cap`, all killed. Rehearsal 1 on the local 4B model crashed the local server (its prompt cache is unbounded and ran out of GPU memory after five conversations); every model run after the crash is archived as an infrastructure failure, filed as the provider's and not the model's; rerun with the server's cache bounded (`--prompt-cache-size 2 --prompt-cache-bytes 3000000000`) | |
| 23 Sep 2026 | 3 (rehearsal) | rehearsal 2 with the local server's cache bounded crashed the server again (GPU memory, 16 GB) after three model runs; what did run exercised the whole path — a real model through the real loop and tools, rejections recorded, the grid scored and reported, every crash filed as the provider's — and found one protocol defect: a reply cut off at the completion limit reads to the model as "decision must be valid JSON", 13 times in a row, never why; now the provider records the endpoint's `finish_reason` on every response and tells the model once, next turn, that its reply was cut off; the grid carries `--max-tokens` (default 1024) as a pack term, room for a decision with its patch; guard `D.cut_reply_is_named`, killed. The local 4B model on this machine cannot rehearse the grid: model quality is measured on the paid model | |
| 23 Sep 2026 | 5 (decision P) | before the paid rehearsal, the pack's worst case was found to omit the judge: its questions were bounded in reply but charged to no cap. Now each judge question is admitted only if its exact worst case — every prompt byte a token, the whole 200-token reply — is within $0.01, and the grid charges that bound once per paid run to the pack cap, in `Decimal`: the final pack's worst case is 108 × ($0.50 + $0.01) = $55.08, the rehearsal's 20 × $0.51 = $10.20; guard `D.judge_question_within_its_bound`, killed | |
| 23 Sep 2026 | 5.1 (pilot-paid-v1) | the paid rehearsal, 20 runs on gpt-4.1 with the final terms: every run `submitted`, no bound hit, no provider failure, no reply cut off, every full-arm tool result OK, lower bound $0.48 in all. Two machinery defects, fixed: the judge's reply `correct; …` was refused for its separator, so one accepted repair went unscored; and the evidence gate told a tool-less alert-only model to "cite only the evidence_id of tool results you received" when it had received none, and one run spent seven turns citing its refusal — the reason now names what may be cited, or says none. What the model decided — REPAIR 0/4 on the full arm, three of them NO_REPAIR after observing the failed load — is the model's, and nothing was changed for it. The rehearsal is excluded from every reported result | |
| 23 Sep 2026 | 5 (decision M2) | the provider speaks to a reasoning model: `--reasoning-effort` on the runtime, the grid (a pack term, set only when given, so an earlier pack still resumes) and the pre-flight, sent in place of `temperature`; the completion bound travels as `max_completion_tokens` for every paid model; gpt-6-sol and gpt-6-luna priced under `openai-list-2026-09-22`, their encoding unpublished and taken as byte-level on two checks — the pre-flight's reserve premise against a real bill, and every bill against its reserve; the pre-flight's `--spend` asks in the run's own shape (`--max-tokens`, `--reasoning-effort`); three guards, all killed | |
| 23 Sep 2026 | 5.1 (pilot-paid-v2) | the Sol rehearsal, 20 runs at effort low: every run `submitted`, every finish `stop`, no reply cut off, no bound hit (the longest run 16 of 20 turns), every run scored, lower bound $0.76. Sol accepted the request shape — effort, no temperature, `max_completion_tokens`. One machinery defect, in two parts, fixed: 26 of Sol's tool calls carried text after the call's JSON — stray tokens, and three times a tool result it wrote for itself — and the loop refused each rightly but said only "invalid tool-call envelope", and, the executor never seeing the call, the refusal reached the archive only inside the next request's messages; now the refusal says the call must come alone and that a result is the tool layer's, and a call the executor never sees is recorded by the loop in the runtime's history, `tool_call` and `tool_result`; guards `A.refused_call_is_in_the_history` and `A.call_then_text_is_named`, killed. A finding, not acted on (decision P): on all four REPAIR incidents Sol found the failed load and the missing orders, and escalated — it read the staging cutoff at loader-acknowledged lines, which the transform's comment calls intentional, as a contract a repair should not rewrite; gpt-4.1 in pilot-paid-v1 answered NO_REPAIR on three of the same four. The keys stand; the evaluation report says what both models did | |
| 23 Sep 2026 | 2 (decision B) | the load-stopped family burned and replaced: `python -m adii.examples.canonical_world` writes a fourth state, transform-defect — every order delivered and loaded, the staging change DATA-97 dated from the day leaving live distributors out, the same alert and drop as its siblings — and keeps writing the burned state byte for byte; six keys and grounding keys authored and frozen, six oracles; `catalogue/burned.json` names the burned six and the grid's default pack leaves them out; the readiness gate proves the validity rule on every REPAIR case, and the scale ladder measures the live states; guard `C.burned_never_in_a_default_pack`, killed | |
| 23 Sep 2026 | 2 (decision E) | the partition registered: `catalogue/partition.json` names the benchmark's 12, the held-out 6 and the demo 3, `burned.json` the other 6; the grid runs a partition by name, the benchmark by default, and named incidents only for a rehearsal; the generator writes a seventh company, aug, in the three live states for the stage, its keys, grounding keys and oracles frozen with it; the readiness gate holds every case, the validity rule on all seven REPAIR cases, and the partition — whole, two and one per stratum, and no held-out or demo case in any committed pack receipt. The burned-case guard is retired with the code it guarded: the default is now the registered benchmark, held by that test | |
| 23 Sep 2026 | 5.1 (pilot-paid-v3) | Luna qualified on the burned cases, which no result reports: 6 runs of gpt-6-luna at effort low, every run `submitted` and scored, every tool call OK, no malformed call, every finish `stop`, $0.017 in all; its one refused submission was the protocol — a REPAIR without a patch, told so, then an escalation. No machinery defect. Luna, like Sol, escalated every burned case, quoting the transform's deliberate staging cutoff | |
| 23 Sep 2026 | the front door (F1, F2) | the record carries the chart: every canonical package writes `alert_series.json`; the runtime records `alert_observed` before the investigation; the validator returns `rebuilt_series` from its rebuild; the record is `adii.run_record/v3`. Proved on the real packages: the runtime's reading shows the drop and is no tool call; the restored staging brings the day back to what was delivered in the validator's own series, and the chart-only fake paints the same day back and is still rejected; guards `D.alert_is_observed_before_the_investigation` and `C.validator_reports_its_rebuilt_series`, killed | |
| 23 Sep 2026 | the front door | the new page wired to the real backend: the old page archived whole in `03_assets/archive/front-door-v1/`; `web/view.js` projects every word from the record and `web/app.js` only draws, with text nodes; the symptom chart from `alert_observed` above the answer and never among the evidence, "How ADII knows" the cited observations only and "Investigated" everything, "Independent rebuild" from `rebuilt_series` with the validator's checks, a layout per answer, sign-off from the authorities' facts, the "no answer" screens from the termination; fonts and logo served locally (OFL), "ADII — Is it broken?" beside the unchanged mark; the demo server takes `--reasoning-effort`. Building it found one defect in F2, fixed: a patch that reshapes what the series query reads made the validator raise, filing the run as an infrastructure failure — the series now comes back empty and the verdict stands. Tests rewritten: the projections in node over real runtime records, the design rules, the executing payload and the fit at 1440 and 390 in Chrome, and both entry paths in the browser against a stand-in model, the page's record the archive's by digest; guards `D.page_renders_text_never_markup` (moved), `D.how_adii_knows_is_what_was_cited`, `D.a_fix_stands_only_with_both_authorities`, `C.the_series_never_costs_a_verdict`, all killed | |
| 23 Sep 2026 | the front door (integration gate) | the three answers driven through the browser by the project owner against gpt-6-sol at the final settings, on the demo company's cases: Fix it (16 of 20 turns, $0.104 — proposed, allowed, accepted; the validator's rebuild brings 18 Aug from $2,741.46 to $5,541.40), Leave it (10 turns, $0.052), Escalate it (13 turns, $0.078); each downloaded record byte-identical to the archive's, the downloaded fix equal to the record's patch, every citation minted by the tool layer, the page's projections equal to the record's facts. Sol's stray text after a call recurred, two or three times a run, each refused and recorded — turns it costs, within the registered twenty. The run without an answer was not driven live, by the owner's call: its screens are held by the projection tests over every ending and by the fit test in Chrome. The FIX record is kept as the precomputed stage case | |
| 23 Sep 2026 | 4 | prices verified on OpenAI's pricing page before the freeze: gpt-4.1 $2/$8, gpt-4.1-mini $0.40/$1.60, gpt-6-sol $2/$10, gpt-6-luna $0.10/$0.50 per million — the tables unchanged. `python -m adii.evaluation.lock` built (the freeze file, `--check`, the four registered packs' terms), the grid's gate on registered packs, `test_the_freeze.py` as the standing rule, and `02_src/scripts/package_submission.py`; guard `C.registered_pack_runs_only_on_the_freeze`, killed | |
| 23 Sep 2026 | 2 (decision A2) and the front door | a review found the alert's percentage was the orders' under the word revenue, so the page showed 49% above a chart reading 51%; version 2 of the 21 live cases written with an alert that names the orders, keys, grounding keys and oracles copied and frozen, the partition moved, version 1 superseded and kept; the readiness gate proves the new alert matches the orders in every state and version 1 unchanged. And the stage leak: the list showed earlier answers under the neutral samples, so `#new` — what "New investigation" opens — is a launch view with no earlier answer on it, held by the fit test; the history stays one click away. The stage's precomputed FIX (version 1, `revenue-drop-d0888f-20260923T190024-097Z`) stays as it is; a version-2 film case is run only after the freeze | |
| 24 Sep 2026 | before Freeze A (the audit) | a production-readiness audit of every file, by five read-only reviewers, each finding verified against the code before acting. Fixed on the evaluated path: a tool call or decision carrying NaN, Infinity or a 5,000-digit number crashed the run instead of being refused; the database misfiled an unbound placeholder as "one statement per call" and a closed connection as the model's mistake, and did not escape a quoted table name; a refused or over-long declared series escaped the runtime after its label was claimed; the provider worker leaked on an unexpected exception and the trace file was never closed; the pre-flight's model listing followed a redirect carrying the credential; the manifest did not keep `alert_series.json`; the newest freeze was chosen by name; `--partition` offered demo and superseded; a judge on a local pack was uncapped; the packager took run folders by prefix; the 48 scored keys were not schema-checked. The page and server: the page may start only the samples and the walkthrough (a held-out case could have been run from it); an older record's accepted repair was shown as rejected; check marks were read from prose; spend was shown as spent, not as a lower bound; a dead run looked alive; a slow answer could redraw another screen; a negative Content-Length bypassed the body bound. Removed as unused or superseded: feedback, page-chosen run settings and the evaluation endpoint (decision R), and the evaluation modules `failure_signal`, `receipt_artefacts`, `commitment`, `exposure`; the fake validator moved into the tests. One reported defect was not one: a judge-settled "incorrect" repair filed as a rejection is the team's pinned decision, and only its comment was wrong. A correction to this log's 23 Sep row "13 skipped (the blind-key tests, kept out on purpose)": they skipped on a stale path; they run now. Docs and docstrings brought to the system as it is; the ZIP holds only what a judge needs (`export-ignore`), named `ADII_Group05_Code_v1.zip` | |
