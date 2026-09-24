> **Historical, 24 Sep 2026.** The D track's plan as written in week 2: its six-week clock, its blind run and its dates were replaced by [final_plan.md](final_plan.md) (decisions E and F). Kept as the record of what was planned; read the final plan for what holds.

# Plan: telemetry, integration and hardening — the D assignment

**Scope.** The D row of the assignments table in [inherited/CONFORMANCE.md](inherited/CONFORMANCE.md):
D1–D15, provider and freeze integration, X2, X4, X3 if applicable, and the X1 guard-removal
pass across A, B, C and D before freeze. Plus the work no letter names and the runtime cannot
ship without: the end-to-end runtime ([build_plan.md](build_plan.md) M7), CI and the
environment, the demo, and the submission's front door. One teammate covers A, B and C. This
document is for everything else, starting from D.

**Clock.** The repository started on 5 September 2026 and M0 landed in week 1. Five weeks
remain: **14 September – 18 October 2026**. Every unit below is dated against that.

**How to use this.** Each unit is one PR its author can defend with the five questions in
[review_playbook.md](review_playbook.md). Copy a unit into [task_template.md](task_template.md)
before starting it. The "done when" column *is* the acceptance test; if it cannot be run, the
unit is not specified yet.

**The frontend is an operational surface, not a teaching page.** We are in building mode:
the day a real provider call produces a run, the inspector has to show it — the transcript,
every tool call paired with its result and status, the termination reason, the verdict, what
it cost and on which model. So the inspector is built on the run record (D-2) in week 2, the
runtime writes that record from week 3, and `/` is the run browser. The nine-chapter learn
page and the five hand-authored fixtures were deleted on 13 September; the walkthrough run
is the first record. The browser is read-only over the archive: runs are launched from the
command line, and nothing a page can do spends money or creates a first exposure (D8).

---

## Where D stands on 14 September

The 13 September table this replaces is in the history of this file. One day later:

| Exists | Missing |
|---|---|
| `RunRecord` v1 in `reporting/record.py`: strict JSON, a schema version, a label that is one path segment, a termination class, provenance read at write time (D3, D4, D14) | D-1, the event vocabulary, and D-3, evidence citations — the four decision rows in [trace_event_contract.md](trace_event_contract.md) are open |
| the archive `01_data/runs/<label>/record.json`: the label reserved before the run, one record for every ending, a reserved label with no record listed as such (D1, D5, D6) | the tracked manifest of what the archive holds (D13, unit D-10) |
| the runtime: investigator → tools → validator on a harness-owned trace, counters from the trace, an exit code per outcome; the tools are B's real executor over the walkthrough world, evidence ids on every observation | a provider, a receipt before the first paid call, a cost ledger with unknown rows (D7, D8, D15; units D-11, D-12, D-15); model turns and cost are zero because no model runs |
| `render_run()` from the record, every ending in its own terms, a call the run died on shown as unanswered; one committed fixture per ending under `01_data/walkthrough/endings/` (D11) | budgets and bounds (D9, unit D-9) |
| the inspector: run list, filters, side-by-side compare, the identity design system from `03_assets/identity/`, read-only, proven in a real browser to execute nothing a model wrote (D11, D12) | the drawer's fingerprints and ledger rows (with D-11, D-12) |
| CI on Windows, macOS and Ubuntu with a per-test timeout; every test collected, every import declared, every dependency a chosen name (X4, X2, D10) | the SDK floor job and the guard-removal pass (X2, X1; units D-13, D-18) |
| A's investigator loop, merged 14 Sep (PR #12): a scripted provider seam, a turn budget, a stop signal, structured decisions with an evidence gate, eight trace kinds of its own, two ending exceptions | A wired into the runtime through one canonical trace adapter, after D-1; a termination class for a stop without a decision; a provider behind A's `respond` seam (D-11) |

The first line of [../adii/reporting/README.md](../adii/reporting/README.md) still holds: if a
behaviour is not in the trace, nobody can prove it happened. Since 13 September the runtime
writes the trace and the archive keeps it.

## The shape of D — six pieces

```text
A / B / C  ──TraceEvent──▶  events.py    the vocabulary: which kinds exist and what each
                                 │        payload holds. This is what A, B and C emit.
                                 ▼
                             record.py   RunRecord v1: strict JSON, versioned, no machine paths
                                 │
                                 ▼
                             archive.py  the sink: every exit path leaves a classified record
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
          render.py          ledger.py          receipts.py
          the report         cost as three      written and flushed before
          (D11, D12)         evidence classes   anything irreversible (D8), and
                             (D15)              the manifest of what exists (D13)

   scripts/guard_check.py    X1 — neutralise a guard, run the suite, restore, name survivors
   CI                        X4 — one command, every change, a timeout that fails not blocks
```

CONFORMANCE says D is **passive**: it records what A, B and C say and never reinterprets. So
D's first deliverable is not code they call — it is the vocabulary they emit. That is also
what makes this plan independent of their schedule: everything below is built and tested
against the walkthrough fixture and scripted stand-ins before any of A, B or C exists, exactly as the
walkthrough already does.

---

## Six decisions to settle in week 2, before code

1. **The trace event vocabulary.** Drafted as [trace_event_contract.md](trace_event_contract.md)
   for the team to approve before any constructor lands: requests and responses as separate
   events, observation ids minted by the tool layer, a termination set owned by the loop,
   and the `TraceEvent` envelope unchanged. A, B and C then build events only through D's
   constructors in `reporting/events.py`. *14 Sep:* the four rows are still open. B's tool
   layer already mints an id per OK observation, named `evidence_id`, from the tool, its
   arguments and its content — row 2 has an answer under a different name than proposed.
2. **Where the model-provider adapter lives.** Boundary 1 forbids network access outside
   `tools/`, `examples/` and `reporting/`, and the loop needs a model. Recommendation: a new
   `adii/provider/` package, the only place a model SDK is imported, added to the allow-list
   in [../tests/architecture/test_boundaries.py](../tests/architecture/test_boundaries.py) by a
   reviewed change; A programs the loop against a small `Provider` protocol with a scripted stand-in; D
   builds the real adapter (D7, X2). The SDK itself is the repository's first runtime
   dependency and is a review item on its own. An OpenAI-compatible local endpoint uses the
   same adapter, which gives free development runs.
3. **Where records live.** `01_data/runs/<label>/` for payloads, ignored by git;
   `01_data/runs/MANIFEST.json` tracked. The ignore rule gets a comment saying that ignoring
   is not preserving (D13), because that is where the next person will read it. The
   inspector's server reads this directory and nothing else.
4. **A per-test timeout.** `pytest-timeout`, pinned in `requirements.txt`, with
   `timeout_method = "thread"` — the signal method does not exist on Windows (X4). A test
   that exceeds the budget is refactored; the budget is not raised. *Done 14 Sep (D-5).*
5. **X3 does not apply today.** There is no caller-keyed server state anywhere — the demo
   server keeps none. Recorded here so it is a decision rather than an omission; it comes
   back the moment anyone adds a rate limiter or a per-client cache.
6. **The UI package.** `adii/demo/` becomes the operational inspector the moment it reads
   real records. Its boundary stays — nothing in `adii/` imports it, and a test enforces
   that — so the path can stay until M7 and be renamed mechanically then. What changes now
   is its contract: the inspector renders `RunRecord` v1 and nothing else. The demo-only
   fields (`intro`, `mechanism`, `plain`, and `evaluation` unless a record was actually
   scored) retired with the `contracts/demo/v0` shape on 13 September. *14 Sep:* the
   inspector runs on the identity design system delivered to `03_assets/identity/`; its
   three stylesheets are copied in by `scripts/sync_identity.py` and held byte-identical
   by a test. Dark by default, violet for interaction only, read-only stays.

---

## The build, in units

Phases follow the build order CONFORMANCE gives D: record, then sink, then receipts and
preservation, then provider. Within a phase the order is the dependency order.

### Phase 1 — the record · week 2 (14–20 Sep) · feeds M1, M2, M7

| # | Unit | Done when | Ids |
|---|---|---|---|
| D-1 | `reporting/events.py` — one constructor per event kind; the payload is validated once, at construction; an unknown kind is refused | every constructor yields a strict-JSON payload; the walkthrough trace round-trips through the constructors unchanged | D1, D2 |
| D-2 ✔ 13 Sep | `reporting/record.py` — `RunRecord` v1: schema version, incident context, the `InvestigationRun`, configuration, provenance; `to_json` with `allow_nan=False` and no fallback hook; `from_json` dispatches on version | NaN or Infinity is rejected *before* the sink; an unknown version is refused, never guessed; a committed v1 fixture loads; no record matches an absolute-path pattern; the source revision is read at write time, not cached | D3, D4, D14 |
| D-2b ✔ 13 Sep (over v1 as it stands: no model turns and no evidence ids exist until D-1 is agreed, and only the submitted class has a record to render) | The inspector on the record — the server lists and serves `RunRecord` v1 from `01_data/runs/`; `app.js` renders v1 only: the transcript (model turns and tool calls, each paired with its result and status), the decision with the evidence ids it cites, the patch, the verdict, the termination reason, the configuration and the cost; the walkthrough run is the first v1 record so the page has content on day one; `/` serves the inspector | every committed v1 record renders with no field the page invented; a record of each outcome class renders with its own label; nothing in `app.js` reads a demo-only field | D1, D4, D11, D12 |
| D-3 | `reporting/counters.py` — `tool_calls`, `model_turns`, `latency_ms` derived from the trace; a decision's evidence ids checked against the ids the execution layer minted | a run that claims fewer calls than its trace shows is recorded at the true count; a citation to an id nobody minted is rejected | D2 |
| D-4 ✔ 14 Sep (in `reporting/record.py` and `runtime/run.py`; the loop signals its classification by raising `runtime.run.Terminated`) | `reporting/archive.py` — the sink: reserve the label only after every non-I/O precondition passes; classify each exit (scored, model failure, bound, validator rejection, infrastructure failure) and write a record for it; sink I/O failure is terminal and the docstring says so | a run ended three ways leaves a transcript each time with the messages produced so far; a bad payload becomes an archived infrastructure failure and a non-zero exit while the other records survive; a precondition failure leaves the label reusable | D1, D3, D5, D6 |
| D-5 ✔ 14 Sep | CI hardening — pytest-timeout (thread); a test that every directory under `02_src/tests/` is collected and the count is known; a test that every non-stdlib import is declared; a test that no extra names a package we do not own | a hung test fails; a test directory outside `testpaths` fails the build; an undeclared third-party import fails | X4, X2, D10 |

### Phase 2 — the runtime and the report · week 3 (21–27 Sep) · M7

| # | Unit | Done when | Ids |
|---|---|---|---|
| D-6 ✔ 13 Sep (the runtime; the investigator it drives is still a script — M7's composition of A into it is unit D-6b, after D-1) | `adii/runtime/` — `python -m adii.runtime --incident <id> --provider scripted`: investigator → validation → archive → render, in one process. Defines the three protocols it expects from A, B and C. Runs today with a walkthrough replay standing in for the investigator | one command, one incident, one archived record, one rendered report; a distinct exit code per outcome class; green on Windows and macOS | M7 |
| D-6b | The vertical slice — one adapter between A's `run()` and the runtime's `Investigator` protocol: the canonical trace recorded at the provider boundary before A parses the response, A's two exceptions mapped to termination classes, the decided class for a stop without a decision; the scripted stand-in retired | A's loop, invoked by `python -m adii.runtime` with the scripted provider, over B's real tools, leaves one `adii.run_record/v1` with one trace that the inspector renders; every M7 "complete when" box | M7 |
| D-7 ✔ 14 Sep | `render.py` v2 — renders from a `RunRecord`, not from live objects; labels success, model failure, bound hit, validator rejection and infrastructure failure each in its own terms; pairs every call with the result the model saw, in order; a terminal submission is never called "pending" | one committed record per outcome class; each renders with a distinct label; `expected_report.txt` grows one file per class | D11 |
| D-7b ✔ 14 Sep; 15 Sep the information architecture for someone who did not build ADII — a front door on the incidents, a run as a story in a fixed order, every added sentence a tested projection in `web/phrasing.js`, phone width an acceptance test; the drawer's fingerprints and ledger rows arrive with D-11 and D-12 | Inspector, production features — the run list grows with the archive (label, incident, model, outcome class, cost, started); filter by incident and by model; **compare** two runs of one incident side by side, which is how models get tested; the provenance drawer shows requested and effective configuration, one fingerprint per response, and the ledger with its unknown rows | two archived runs of one incident compare on one screen; a run with an unknown-usage row shows its cost as a lower bound, labelled | D7, D11, D15 |
| D-8 ✔ 14 Sep (source-level rule in `test_demo_design_rules.py`; the D12 browser regression in `test_the_page_executes_nothing.py` drives the shipped page in Chrome, which every CI runner ships) | The escape invariant — nothing drawn from a record is interpolated raw into any rendering surface; a source-level assertion that runs without a browser (the demo already has one for its own scripts) | reverting the escape turns the test red | D12 |
| D-9 ✔ 20 Sep, not as a `Budget` object: the bounds live where they bind — `--max-turns` in A's loop, `--max-tool-calls` in the executor (DENIED past it), `--max-model-requests` (as many as the turns when omitted) and `--max-wall-clock-seconds` in the provider (no request past it; the request made by a killable worker process, `provider/worker.py`, cut at the deadline — a trickling body cannot hold the local run; a cut request keeps its reserve), `--max-cost-usd` in the provider as hard worst-case admission in exact `Decimal` (every byte a token at the input rate, `max_tokens` at the output rate, a response without usage charged at its reserve; the request that would cross is not sent — no overshoot; a bill above its reserve is the provider's failure, `ReserveBreached`, and ends the run); each named in its `bound_hit`, all in the receipt and the record, all reported by the page's `/api/launch` | each bound trips with the others slack; the cap run's spend stays within the cap and the refused request is never on the wire; admission against the lower bound would send where worst-case admission refuses; the trickle is cut at the deadline; sixteen guards | D9 |
| D-10 ✔ 16 Sep | `python -m adii.reporting.manifest` — manifest-first preservation: hash the source, copy, re-hash the destination against the manifest made before the copy; verification re-runs from the manifest alone; each artefact declares its retention class | a payload change without a manifest change fails a test; the original is never deleted on the strength of an unverified copy | D13 |
| D-10b ✔ 16 Sep | retention classes for what a run leaves beside its record: `receipt.json`, `trace.jsonl` and `record.json` are **evidence** — the run's own; `feedback.jsonl` is an **annotation** — what a person said afterwards; `evaluation_report.json` is an **evaluation** — what the authority said against a key the run never saw; since 17 Sep `incident.json` and `world.sql`, a brought incident's, are **evidence** too, and since 20 Sep so are its evidence bundles (the map files and every file under their `*_sources/` folders). All of these are attested and preserved; a file under any other name or folder in a run's folder is an unlisted finding | preserving an archive drops nothing a run left; a test removes each artefact and verification names it, and plants a stranger and verification lists it | D13 |

### Phase 3 — provider and money · week 4 (28 Sep – 4 Oct) · M8

| # | Unit | Done when | Ids |
|---|---|---|---|
| D-11 ✔ 17 Sep (`--provider openai`: model priced, cap above zero, https and no secret in the endpoint, credential from `OPENAI_API_KEY` — each checked before the label is claimed, each a guard; the requested configuration — model, temperature, max_tokens, timeout, cap, price table, credential *name* — in the receipt and the record; the fingerprint recorded per response, null when absent; the key on the wire and in no artefact, pinned by a test that greps the run folder and a 401 whose body echoes the masked key) | `adii/provider/` — configuration validated before the client is built; requested *and* effective configuration recorded; one fingerprint slot per response, nullable | with the credential absent *and* the model id absent, the error names the model id; a run with N responses stores N fingerprint entries; a null fingerprint is recorded as null, not omitted | D7 |
| D-12 ✔ 17 Sep, pre-empting row 1 as the spike did (usage read from `model_responded`, matched by turn, null when absent; `reporting/ledger.py`: proved usage at nominal prices pinned per model id with a table id, every other row unknown; the record's `api_cost_usd` is the lower bound and both renderers say "at least $x (n request(s) without usage)", never $0 for a paid run; the provider admits each request against `--max-cost-usd` by its worst case and ends the run as a `bound_hit` before the request that would cross — since 20 Sep, no overshoot — the third class, "failed before the provider", and the open-job case wait for a provider that has them) | `reporting/ledger.py` — three evidence classes: proved usage, provider-confirmed without usage, failed before the provider; a client-side timeout is never in the third class; a submitted job stays open until fetched or written off; nominal prices pinned per model id | a synthetic ledger with one proved response, one timed-out attempt and one uncollected job aggregates to a value tagged lower-bound with two unknown rows; an untagged total fails | D15, D9 |
| D-13 | X2 floor job — a CI job that builds an isolated environment at the declared SDK floor and asserts every pinned parameter is accepted and every advertised module imports; versions compared with a parser, never as strings | the job is green at the floor and red one version below it | X2 |
| D-14 ✔ 17 Sep, by type (A raises `ProviderFailureError` *from* the provider's exception; the runtime reads the cause's type — `ProviderFailure` → `infrastructure_failure`, `BoundExceeded` → `bound_hit`, anything else → `model_failure` — never the message; HTTP 401/429/500, a redirect, a timeout, a worker that cannot be started and a 200 whose body is not the API's shape are the provider's failure, exit 4, and the three renderers say "outside the model"; the model is blamed only for what a well-formed response says — 20 Sep) | Outcome classification is A's word — a bound hit, a model failure and a platform failure each travel from the loop to the archive unchanged; D adds no interpretation | walkthrough variants for each termination reason land in the record verbatim | M8, A5, A9 |

### Phase 4 — freeze and the blind run · weeks 5–6 (5–18 Oct) · M9, M10

| # | Unit | Done when | Ids |
|---|---|---|---|
| D-15 ✔ 16 Sep (D's four fields; the evaluation authority's frozen identifiers join `artefacts` when a run is scored — C's `receipt_artefacts.py` is that half) | `reporting/receipts.py` — before any irreversible call a receipt naming the artefact digests, the configuration, the source revision and the reason it is permitted is written *and flushed*; retained on the failure path | kill the process after the receipt write and before the call: the receipt exists and names what was about to be spent | D8 |
| D-16 | `python -m adii.freeze` — records digests of the model-facing surface (prompts, tool schemas, configuration) and of the scoring code as *separate* artefacts, because they freeze at different times ([inherited/AUTHORITY_LIFECYCLE.md](inherited/AUTHORITY_LIFECYCLE.md)); a test that a frozen digest still matches | the three M9 checkboxes | M9, C3 |
| D-17 | The grid runner — N incidents × R repeats; every promised repeat is materialised as a record, success or classified failure; one failing unit does not abort the rest | a unit failing mid-grid leaves a classified record for every promised repeat and the remaining units still run | D5 |
| D-18 ✔ 16 Sep (20 guards across A, B, contracts and D, all killed; C's join on merge; a CI job runs the pass on every pull request) | `scripts/guard_check.py` — a registry of named guards across A, B, C and D (file, exact snippet, neutralised snippet) plus controls; neutralise, run pytest, restore; survivors listed by name; non-zero on any survivor or on a control that survives; a registered snippet that is not found is itself a failure | a deliberately kept survivor fails the pipeline; runs in CI before freeze | X1, X1a–c, X4 |
| D-19 (the seam ✔ 16 Sep: `python -m adii.evaluation --run L --key K` scores the record the runtime wrote, through its own reader, against a frozen key, and keeps `evaluation_report.json` beside the record in its own retention class; the page serves it and says the category in the authority's terms; the M10 grid itself waits on D-17 and a key per incident) | The M10 report — from C's scoring output: success, failure, false repair, correct abstention, unnecessary escalation and repair rejection, each labelled in its own terms | one archive of each class renders distinctly and completely | D11, M10 |

X1a, X1b and X1c are review questions D asks of every guard in the registry, not code: is
the check independent of the code it checks; are the boundary cases named tests rather than a
count of random trials; is prevention tested at the boundary with the downstream checks off.

### The data lane — in parallel with the engineering lane

Proposed 14 September in [development_catalog.md](development_catalog.md), for the team to
resolve before any of it is built. The investigator will outrun the walkthrough fixture the
day it exists, so the catalogue runs beside the engineering lane rather than after it:

```text
PRIVATE — can start now, needs no team decision
P-0   partition the discovery corpus into reserved and declassifiable
P-1   write and hash the reserve commitment (adii.reserve_commitment/v1)
        │  the immutable boundary
        │
TEAM — blocked on the seven rows in development_catalog.md
        ▼
D-20  the reserve commitment enters the repository and is verified
        ▼
D-21  the receiving machinery: loader and guard tests
        ▼
D-22  six qualified development incidents, compiled and declassified
        ▼
      A develops against them  →  freeze  →  reserved material  →  blind evaluation
```

The order is the point: the private commitment precedes the first development incident in
git history, so "reserve first" is true in the execution graph and not only in prose.

| # | Unit | Done when | Ids |
|---|---|---|---|
| D-20 (the receiving side ✔ 17 Sep: `evaluation/commitment.py` — the private partition, every candidate to `reserve` or `development_candidate`, canonicalised and digested; the team-visible document carries the digest, the counts, the campaign and the custodian, never an assignment; `--verify` re-derives the digest from the private original; made once. Waits on the custodian's partition and document) | The reserve commitment received — the custodian's `adii.reserve_commitment/v1` document and its digest committed under `02_src/adii/evaluation/`, verified against the private original by digest | the file exists in the repository and predates every development incident in git history; the digest matches the custodian's | D8, D13 |
| D-21 | The receiving machinery — `python -m adii.runtime --incident <id>` loads `01_data/incidents/<id>/` through the tool layer's world opener; the guard tests: every incident has a truth file marked `public_development` with a public `development_selection_class`, and nothing in the repository is blind-eligible. *Half built, 17 Sep, for a different class of incident:* `--incident-dir DIR` loads `incident.json` + `world.sql` — the folder shape a declassified incident can reuse — for the operator's own, brought from the page (`tools/user_world.py`), kept beside the record, no evaluation claim; the catalogue loader and its two guard tests remain, after the seven rows resolve | the walkthrough still runs by its own path; a compiled incident runs end to end with the scripted provider; both guard tests are red against a planted violation | D1, X4 |
| D-22 | The declassified development catalogue — six incidents compiled by the custodian from the private corpus into the receiving contract, one per selection class, each passing the four questions, reachability tested against the real tool layer | six records in the archive, one per incident, each rendering in the inspector with its own disposition; additive from then on | M3, M4, M5 |

### Everything else, in parallel

- **When B's world lands** ([DATA_WORLD_v0.md](DATA_WORLD_v0.md)), real runs against it
  replace every hand-authored record, and the front-door invariant tests move to those
  runs. Until then the inspector shows the walkthrough run and whatever the runtime has
  archived.
- **Screenshots** of real runs into `03_assets/screenshots/` for the presentation.
- **Housekeeping** that only D notices: GitHub handles in `CODEOWNERS`, the generated docs
  staying generated, `current_status.md` regenerated with every package that grows.
- **The live spike**, 15 Sep, branch `spike/live-local`: `adii/provider/` behind A's seam
  over a local OpenAI-compatible endpoint, `runtime/live.py` driving A's loop from the
  runtime, `--provider local`. One trace, recorded at the provider and tool boundaries. It
  pre-empts D-1 in code on purpose, as working evidence for the review, and makes the one
  policy choice main must not (a stop with no decision → `model_failure`). It was meant to
  stay on its branch until the rows resolved; it reached `main` on 16 Sep with the live
  console (PRs #20, #21, #23). So its placeholders are on the main command line and in the
  page's launcher, marked SPIKE in the code, and D-6b replaces them in place once rows 1,
  5 and 6 are decided. Nothing produced through them is quoted as an ADII result.
- **Frontend specimens**, 15 Sep: `python -m adii.examples.specimens` archives six
  hand-authored development incidents with ten scripted runs, produced through the real
  runtime and B's tools, every record marked scripted with no model and no evaluation
  claim. They exist so the inspector is designed against a portfolio, not one fixture.
  They are not the development catalogue ([development_catalog.md](development_catalog.md))
  and are replaced or supplemented by it once its rows resolve.
- **The identity and design system** lives in `03_assets/identity/`, delivered as an
  archive only — a loose SVG from a chat arrives stamped with a content credential and
  files go missing. The inspector's stylesheet is a synced copy; the specimens there are
  the reference for components the record cannot feed yet (receipts, per-check verdicts,
  evidence slots), which stay off the page until their data exists.

---

## What D needs from A, B and C, and by when

| From | What | Needed for | By |
|---|---|---|---|
| A | build every event through `reporting.events`; a typed termination reason on every exit (bound hit, model failure, submission); no self-reported counters; enforce `Budget` | D-6, D-9, D-14 | week 3 |
| B | evidence ids minted in the execution layer and carried in `tool_result` events; the four statuses verbatim | D-3 | week 3 — landed 13 Sep, as `evidence_id` in every OK observation; the runtime drives it since 14 Sep |
| C | failure signals for the grid; freeze identifiers (answer-key digests) for receipts; the shape of scoring output | D-15, D-17, D-19 | week 5 |

Until each lands, the corresponding unit is tested against the walkthrough fixture and a
scripted stand-in. Nothing in this plan waits on another track to start.

---

## Week by week

| Week | Dates | Lands |
|---|---|---|
| 2 | 14–20 Sep | the six decisions agreed in writing; D-1 to D-5, with D-2b the first thing anyone can open in a browser. *Landed 13–14 Sep:* D-2, D-2b, D-4, D-5, and from week 3 D-6, D-7, D-7b, D-8; D-1 and D-3 wait on the decision record |
| 3 | 21–27 Sep | D-9 and D-10 remain of this week's units; M7 already runs end to end and the runs appear in the inspector |
| 4 | 28 Sep – 4 Oct | D-11 to D-14; the first real provider run happens only after D-15's receipt exists, so D-15 moves forward if that day comes early |
| 5 | 5–11 Oct | D-15 to D-18; the guard pass over every A, B, C and D guard; freeze |
| 6 | 12–18 Oct | D-19; the blind run; the report; demo re-pointed; submission packaging |

---

## Done means

Every checkbox in [build_plan.md](build_plan.md) that telemetry or integration answers for:
M1 "every turn appears in the trace"; M2 "the trace records the request and the result";
all four of M7; M8 "a model error is recorded as a model error" and "cost and latency are
measured from the trace"; M9 "hash recorded"; M10 "the report shows … with equal honesty".

Every D and X requirement has a test that names it, and the guard pass lists no survivor.
The inspector at `/` shows every archived run, with no field the page invented, and can put
two runs of one incident side by side.

```bash
python -m ruff check 02_src
python -m pytest
python -m adii.runtime --incident demo-learning-001 --provider scripted
python 02_src/scripts/guard_check.py          # every guard killed, none surviving, by name
```

---

## How this plan fails, and what stops it

- **Waiting on A, B or C.** It does not: scripted components and the walkthrough fixture come first, and
  the runtime's protocols are the written interface the other track builds to.
- **A contract change turns out to be needed** — a termination reason or a schema version on
  `InvestigationRun`, say. It is not: the trace carries the reason and the record carries the
  version. If one is ever genuinely needed, it goes through cross-boundary review in week 2,
  never in week 5.
- **Windows.** Paths, file locks, flush semantics and the missing signal timeout. Every
  unit's tests run on both platforms from its first PR; `pathlib` and `newline="\n"`
  throughout; no shell anywhere.
- **Real money spent without a record.** The runtime refuses any paid provider unless a
  receipt was written first. D-15 is a precondition of D-11 going live, whatever the week.
- **The browser becoming a launcher.** It became one on 16 September, on purpose and
  narrowly: only when the operator starts the server with a local model, only against that
  endpoint, with the receipt written before the investigator runs (D8). On 17 September,
  with D-11 and D-15 built, the paid path followed under the same shape: the operator
  starts the server with `--provider openai`, a priced model and a cap, the credential in
  the server's environment and checked before the port is bound; the browser sends the
  incident id and, within the operator's flags, a priced model, a cap and a turn budget —
  refused when above them, never clamped — and the run goes through the runtime's own
  entry point, its receipt saying it was requested from the page and within what.
- **The guard registry drifting from the code.** A registered snippet that is not found fails
  the harness, because a guard that moved is a guard that may be gone.
- **Reporting a number that is not ours.** The report labels every figure with the run it came
  from; nothing from `inherited/` is rendered as a result.
