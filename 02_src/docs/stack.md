# The stack — what is built, what is not

One page, dated **15 September 2026**, so nobody has to infer the state of the system from
package names. `current_status.md` is generated and counts lines; this says what the lines
do and what is missing. When the two disagree, the generated one is right about size and
this one is stale about substance — fix this one.

## The shape

```text
             ┌────────────────────────────── 02_src/adii ──────────────────────────────┐
 operator ─▶ runtime ─▶ investigator ─▶ tools ─▶ (world)      ▶ validation ▶ reporting ─▶ archive ─▶ demo (browser)
               │            │              │                         │            │          01_data/runs
               │        provider ─▶ model  │                    (scaffold)    record.py
               │        (spike, local)      evidence ids                         render.py
               └── one trace, recorded at the boundaries ─────────────────────────────┘
                                                    evaluation (scaffold): incidents, truth, scoring — never on this path
```

Python 3.12, standard library only at runtime. No framework, no build step, no database
server, no container. Windows and macOS are both first-class; CI runs on both plus Ubuntu.

## Backend, package by package

| package | lines | state | what exists | what is missing |
|---|---:|---|---|---|
| `contracts/` | 154 | **complete, frozen by review** | the eight shared types and their invariants | changes only through cross-boundary review; `evidence_refs` is proposed (trace contract row 3) |
| `tools/` | see `current_status.md` | **built** (B) | executor with the four statuses, read-only SQLite behind an authoriser; six tools — `get_schema` (with a declared operational schema when the incident carries one), `run_sql`, `get_transform`, `get_notice`, `get_change_history`, `read_reconciliation`; bounded results and an evidence id on every OK observation; one closed-bundle loader (`packages.py`) behind the five evidence kinds; the walkthrough world; an operator's CSV files as the same kind of world (`user_world.py`) | the candidate-repair sandbox; tools over logs and manifests; the canonical operational world |
| `investigator/` | see `current_status.md` | **built and runtime-driven** (A) | the canonical loop, provider seam, frozen state, a turn budget, an explicit stop, structured decisions with an evidence gate, credential redaction; `run_incident` supplies `Recorder.watch(tools)`, so live tool calls and results enter the canonical trace | `permitted_write_paths` not enforced — both recorded live models wrote outside them |
| `runtime/` | see `current_status.md` | **built** (D) | one command per incident; the canonical investigator adapter; a harness-owned trace; counters from the trace; the label reserved before the run; a record for every ending; exit codes per outcome; scripted stand-ins; local and paid provider paths; `--incident-dir`: the operator's package copied into the run folder first and loaded from that copy — the model's view, the receipt and the archive one read of one package; every evidence bundle attested and preserved with the record; a package that fails in the window releases the label; six run bounds — turns, tool calls, model requests, wall clock, a hard cost cap by exact worst-case admission, max tokens — each its own flag, in the receipt and the record, forwarded and reported by the page | independent validation |
| `provider/` | see `current_status.md` | **spike; the paid path built 17 Sep, the bounds hard since 20 Sep** | A's seam served by any OpenAI-compatible endpoint — on this machine without a credential, or paid: receipt on disk required, a nominal price and a finite cap, the credential on the wire and nowhere else, failures filed as the provider's, a free pre-flight; the request made by a killable worker process (`worker.py`) so the run's deadline cuts it; the cap hard by exact worst-case admission, a bill above its reserve the provider's failure | C's judge takes a string-to-string callable, which this package should supply, so one place talks to models |
| `reporting/` | 531 | **built** (D) | `RunRecord` v1, strict JSON, versioned, machine-path-free; the archive; the text report from a record for every ending; the receipt written and flushed before every run (D-15); attestation and manifest-first preservation of the archive (D-10) | event constructors (D-1), evidence-cited counters (D-3), the ledger (D-12, after the trace contract says where usage lands) |
| `examples/` | 543 | **built** | the walkthrough; one produced record per ending; six development specimens with ten scripted runs | replaced or supplemented by the declassified catalogue once its seven rows resolve |
| `demo/` | 325 | **built** | the product's server: the visitor's own incident over their CSV files (`POST /api/investigations`) or one of the archive's; lists and serves the archive, `Cache-Control: no-store`; read-only by default; with `--model`, starts runs against the model the operator configured — local, or `--provider openai` under a cap with the credential in the server's environment — one at a time, through the runtime's own entry point, and streams the live trace; an operator's feedback kept beside the record | nothing planned; it stays small on purpose |
| `validation/` | 228 | **built** (C), merged 20 Sep — **on the live path since 21 Sep** (M7 rows 1–3) | `patching.py` rebuilds a brand-new `ReadOnlyDatabase` from the patched SQL, never the investigator's connection; `checks.py`, three atomic checks; `validator.py`, `Validator.validate(context, decision) -> ValidationResult`, the shape `runtime/run.py` requires, with no parameter a rehearsal claim could arrive through; one frozen world (`demo-learning-001`); `as_dict_validator` for offline scoring | a rebuildable world per real incident — today every incident but `demo-learning-001` is NOT_CHECKABLE, said in structure by `reason_code`; authorization — is the target permitted — kept apart from validation, a PASS never implying permission |
| `evaluation/` | 1045 | **built** (C), merged 16 Sep | deterministic scoring against a frozen answer key with a judge for the one open case; freezing, versioning, grounding and schema checks for the keys themselves; the six outcome categories, a failure signal per repeat (D-17), an evaluation report beside the record (D-19), the artefact digests for the receipt (D-15); 117 of its own tests, passing; the seam to the runtime's record: `python -m adii.evaluation --run L --key K` scores an archived run against a frozen key and keeps the report beside the record | a frozen key for an incident the runtime can investigate — none exists; the judge over a local endpoint (the only provider needs the `openai` SDK); `grounding.py` reads `call["tool"]` where the trace says `name` |

## Frontend

No framework, no bundler, no dependency. Four files of ours over three copied from the
identity handoff.

| file | lines | role |
|---|---:|---|
| `demo/web/index.html` | 59 | the shell: masthead, glyph sprite, one `#view`, one script tag |
| `demo/web/app.js` | 566 | three routed screens from the URL hash — the front door (`#`), an incident's runs (`#i/<id>`), a run as a story or two side by side (`#r/<label>[,<label>]`); one renderer for `adii.run_record/v1` and refusals for anything else; no `innerHTML` |
| `demo/web/phrasing.js` | 130 | every sentence the page adds, each a deterministic projection of record fields; product copy |
| `demo/web/inspector.css` | 76 | layout only; no colour |
| `tokens.css`, `base.css`, `components.css` | 1,485 | the identity handoff's, copied by `scripts/sync_identity.py`, held byte-identical by a test |

**Rules the tests enforce:** dispositions are peers; verdict colour only in the validator's
row; endings and absence achromatic; every token declared; no colour literal in our sheet;
no door from string to markup; one `fetch`, guarded; the schema pinned; every added
sentence in the dictionary and listed in the README; no causal wording; a poisoned record
renders as text in a real browser; no horizontal overflow at 1440 and at a true 390 px.

**API:** `GET /api/runs` (one row per run, newest first, unreadable ones listed with their
error) and `GET /api/runs/<label>` (the record, verbatim). The page can start nothing
unless the operator started the server with a model; then `POST /api/runs {incident,
model?, max_cost_usd?, max_turns?}` starts a run — the server's flags are each run's
default and the ceiling a request may not pass; more is refused, never clamped — and
`GET /api/runs/<label>/trace` shows it as it happens. `GET /api/launch` reports those flags
and the models it offers (every priced one on the paid path); a credential is never among them.

## Data

| where | what | tracked |
|---|---|---|
| `01_data/walkthrough/` | the teaching incident, its trace, decision, verdict, report and v1 record; `endings/` one produced record and report per way a run ends | yes |
| `01_data/runs/` | the archive: `receipt.json` then `record.json` per run, whatever produced it | no — payloads; the README and `MANIFEST.json` are |
| `01_data/demo/world/` | the canonical operational world | a work order; not built |
| `01_data/demo/csv/` | every specimen's world as CSV files, the alert beside them — the data to bring to the page's own form; generated from `examples/specimens.py --csv` and held to it by a test | yes |
| in code | six development specimens (`examples/specimens.py`), each with its own tiny world | yes |

## Tests — current count in `current_status.md`, four layers

| layer | tests | what it holds |
|---|---:|---|
| `architecture/` | 158 | the boundaries; the briefing and status page in sync; every test collected, every import declared, every dependency chosen, a hung test fails |
| `contract/` | 8 | the eight types pinned |
| `unit/` | 185 | the loop, the tools, the record, the environment check |
| `integration/` | 106 | the walkthrough, the runtime, every ending, the specimens, the live path against a scripted stand-in endpoint, the inspector's API and design rules, the phrasing dictionary, the browser checks |

Gates, all green on Windows, macOS and Ubuntu: `python -m ruff check 02_src` and `pytest`.
And the guard-removal pass, `python 02_src/scripts/guard_check.py`: twenty registered
guards across A, B, the contracts and D, each neutralised in turn, each killed by a test;
a survivor fails the job by name. C's guards join the registry when the evaluation
authority merges.

## Open decisions, blocking implementation

| decision | rows | blocks |
|---|---:|---|
| the trace event contract, `trace_event_contract.md` | 6 open | D-1, D-3, D-6b, and through D-6b the vertical slice (M7) and any provider work on main |
| the development catalogue, `development_catalog.md` | 7 open | D-20 to D-22; the private reserve commitment can be made now |

## Milestones, from `build_plan.md`

M0 runway, M1 the loop, M2 controlled tools: **done**. M3 multi-step investigation and M4
the structured decision: **partly**, from A's tests. M7 the vertical slice: **open** until
A is driven by the runtime with one canonical trace. M5, M6, M8, M9, M10: **not started**.
