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

## Phase 4 — Freeze

`python -m adii.freeze --pack <name>` writes `02_src/adii/evaluation/freeze/<name>.json`:
digests of the protocol, the advertised tool schemas per incident, the bounds
configuration, the price table id (verified against the provider's page **before** this
step, the table id bumped if it moved), the validator's source and oracles, the scorer's
source and semantics v2, every catalogue key and grounding key, the judge model and prompt
digest, and the code revision. From then on every receipt carries the freeze digest, and a
test asserts the digests still match. Tag `freeze-<date>`.

**Windows qualification, once, on the frozen build.** `python 02_src/scripts/package_submission.py`
(a new script, standard library only: `git archive` of the tagged commit plus the files
the submission names, written as `adii_submission.zip`, with a manifest of its own
contents) run on the Mac; the ZIP extracted on a clean Windows machine — a teammate's, the
Windows rig, or a local VM — and there: `py -3.12 -m venv .venv`, `pip install -r
requirements.txt`, `python 02_src/scripts/check_env.py`, `pytest`, `python -m
adii.runtime --incident demo-learning-001 --provider scripted`, `python -m adii.demo`, and
the browser product path by hand. Anything that fails is fixed and the freeze is taken
again. This replaces the Windows runner in CI.

**Rule.** Any engineering change after this is a new freeze version. A pack scored under
one version is never re-read under another
([inherited/AUTHORITY_LIFECYCLE.md](inherited/AUTHORITY_LIFECYCLE.md)).

---

## Phase 5 — The benchmark

| # | unit | done when |
|---|---|---|
| 5.1 | the paid rehearsal, `pilot-paid-v1` (decision P), after the pre-flight: the final pack's exact model, provider, prices, prompt, bounds and judge, on ten incidents — every family, every truth in both tiers — in both paid arms, one repeat, 20 runs | every cell archived and scored; inspected for defects of the machinery only and fixed; excluded from every reported result; then phase 4 |
| 5.2 | the pre-flight, before 5.1 and again the morning of the paid pack: `python -m adii.provider --check --model gpt-4.1` (free), then `--check --spend` a single time | `completion: succeeded at check time`, the reserve premise holds |
| 5.3 | the paid pack once (decision M2): gpt-6-sol at effort low, five repeats, twenty turns, a 4,096-token completion bound, a $0.50 cap per run, the pack cap in the pack receipt, temperature 0, fingerprints recorded; the judge on the frozen model | every cell archived, scored, attested; `--preserve` to a second location; `MANIFEST.json` committed |
| 5.4 | the pack read against DECISIVE_TESTS as written | D1–D5 each pass or fail, recorded in a new section of release_evidence.md — appended, never rewritten |

This is where the money goes, and nearly all of it: on the order of five dollars for the
runs and cents for the judge. The canonical run the film shows is one of these records,
chosen after 5.4, not a separate paid run. The capstone ships whatever 5.4 says.

---

## Phase 6 — The evaluation report and the product surface

| # | unit | done when |
|---|---|---|
| 6.1 | `02_src/docs/evaluation_report.md`, generated from `benchmark_report.json`: protocol, denominators, repeats, per-disposition results, control comparison, failure taxonomy, grounding, validation, cost, latency, limitations; the claim boundary updated in release_evidence.md by a new section | every number in it traces to a run label |
| 6.2 | the benchmark on the page: `GET /api/benchmarks` serves each pack's report; `#b/<pack>` renders the grid as a table, every cell a link to its run; the admissibility square drawn from a record's two facts; new sentences in `phrasing.js` and the demo README together; a browser test | `test_phrasing.py` and the browser tests green; no sentence the record cannot back |
| 6.3 | one demo configuration, frozen: gpt-4.1, twenty turns, $0.50 per run — the same bounds in the receipts of the runs that are filmed, the runs that are shown live and the runs that were scored | the page's defaults equal the pack's; the filmed run is a pack record by label |

The prototype page is kept only where its code saves time; the front door — what looks
wrong, over the visitor's own files, Investigate — stays, because it is the product.

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

The incident: configuration A for a REPAIR that ends ACCEPT and admissible, or B for a
NO_REPAIR that shows restraint; the files from the package exported as CSV, never an
audience upload. One person speaks, one drives. The spoken line for each ending, including
the failure line: the sentence on screen came from the record, not from us. Recovery for a
hung run rehearsed: it ends at the provider timeout, and the page says so.

### 7.4 The film, at D−3

From the frozen build only: the finished interface, the final numbers, one canonical run
with its label on screen, the last line "if it is not in the trace, it did not happen".
Nothing the film shows changes afterwards; P uses the same build.

### 7.5 Submission qualification — against the exact ZIP

The artefact the bootcamp receives is what is qualified, never a developer checkout.

1. `python 02_src/scripts/package_submission.py` on the tagged commit `submission`; its
   content manifest reviewed by the architect: the three top-level folders, the README,
   the requirements, the preserved run archive the report cites, and nothing else.
2. No secret: `.env.local` and `.env` absent; the key's prefix absent from every file in
   the ZIP, checked by the script and by hand.
3. Extracted on a clean Mac and a clean Windows machine; on each, from nothing: create the
   environment, install the requirements, `check_env.py` prints `Ready.`, `pytest` green,
   the scripted runtime archives a run, `python -m adii.reporting.manifest --verify` on the
   shipped archive prints OK, `python -m adii.demo` serves and the product path works in a
   browser.
4. If anything changes after this, the ZIP is rebuilt and step 3 is repeated on both
   machines. The ZIP that was qualified is the ZIP that is uploaded, by digest.

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
