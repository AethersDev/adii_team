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
| `tools/` | 484 | **built** (B) | executor with the four statuses, read-only SQLite behind an authoriser, `get_schema` and `run_sql`, bounded results, an evidence id on every OK observation, the walkthrough world | the candidate-repair sandbox; tools over logs, manifests, transforms; the canonical operational world |
| `investigator/` | 342 | **built in isolation** (A) | the loop, a scripted provider seam, frozen state, a turn budget, an explicit stop, structured decisions with an evidence gate, credential redaction, its own eight trace kinds | not driven by the runtime yet (D-6b, after the trace decision); `permitted_write_paths` not enforced — both live models wrote outside them |
| `runtime/` | 346 | **built** (D) | one command per incident; a harness-owned trace; counters from the trace; the label reserved before the run; a record for every ending; exit codes per outcome; scripted stand-ins; the live bridge | the canonical adapter that drives A (D-6b); a termination class for a stop without a decision (contract row 5); the receipt before a paid call (D-15) |
| `provider/` | 93 | **spike, local only** | A's seam served by any OpenAI-compatible endpoint on this machine; requests and responses recorded at the boundary | paid endpoints, refused until the receipt (D-15) and the ledger (D-12); lives on `spike/live-local`. C's judge takes a string-to-string callable, which this package should supply, so one place talks to models |
| `reporting/` | 304 | **built** (D) | `RunRecord` v1, strict JSON, versioned, machine-path-free; the archive; the text report from a record for every ending | event constructors (D-1), evidence-cited counters (D-3), the manifest (D-10), the ledger (D-12), receipts (D-15) |
| `examples/` | 543 | **built** | the walkthrough; one produced record per ending; six development specimens with ten scripted runs | replaced or supplemented by the declassified catalogue once its seven rows resolve |
| `demo/` | 109 | **built** | the inspector's server: lists and serves the archive, read-only, `Cache-Control: no-store` | nothing planned; it stays small on purpose |
| `validation/` | 1 | **scaffold** (C) | a README | the validator: rebuild from frozen inputs, accept or reject. A live REPAIR carries "not checked, not accepted" until then. C's branch wires validation as a scoring precondition but does not build the rebuild |
| `evaluation/` | 1 | **built on a branch, not merged** (C) | on `eval-authority`: deterministic scoring against a frozen answer key with a judge for the one open case; freezing, versioning, grounding and schema checks for the keys themselves; the six outcome categories, a failure signal per repeat (D-17), an evaluation report beside the record (D-19), the artefact digests for the receipt (D-15); 117 of its own tests, passing | the move into this package: it sits at the repository root with flat imports, its tests outside the configured path, an answer key outside this package, 96 lint findings CI has not seen, and an undeclared `openai` import — the three failing tests on that branch are exactly these placements |

## Frontend

No framework, no bundler, no dependency. Four files of ours over three copied from the
identity handoff.

| file | lines | role |
|---|---:|---|
| `demo/web/index.html` | 59 | the shell: masthead, glyph sprite, one `#view`, one script tag |
| `demo/web/app.js` | 390 | three routed screens from the URL hash — the front door (`#`), an incident's runs (`#i/<id>`), a run as a story or two side by side (`#r/<label>[,<label>]`); one renderer for `adii.run_record/v1` and refusals for anything else; no `innerHTML` |
| `demo/web/phrasing.js` | 107 | every sentence the page adds, each a deterministic projection of record fields; product copy |
| `demo/web/inspector.css` | 59 | layout only; no colour |
| `tokens.css`, `base.css`, `components.css` | 1,485 | the identity handoff's, copied by `scripts/sync_identity.py`, held byte-identical by a test |

**Rules the tests enforce:** dispositions are peers; verdict colour only in the validator's
row; endings and absence achromatic; every token declared; no colour literal in our sheet;
no door from string to markup; one `fetch`, guarded; the schema pinned; every added
sentence in the dictionary and listed in the README; no causal wording; a poisoned record
renders as text in a real browser; no horizontal overflow at 1440 and at a true 390 px.

**API:** `GET /api/runs` (one row per run, newest first, unreadable ones listed with their
error) and `GET /api/runs/<label>` (the record, verbatim). The page can start nothing.

## Data

| where | what | tracked |
|---|---|---|
| `01_data/walkthrough/` | the teaching incident, its trace, decision, verdict, report and v1 record; `endings/` one produced record and report per way a run ends | yes |
| `01_data/runs/` | the archive: one `record.json` per run, whatever produced it | no — payloads; the README is; a manifest is D-10 |
| `01_data/demo/world/` | the canonical operational world | a work order; not built |
| in code | six development specimens (`examples/specimens.py`), each with its own tiny world | yes |

## Tests — 395, four layers

| layer | tests | what it holds |
|---|---:|---|
| `architecture/` | 118 | the boundaries; the briefing and status page in sync; every test collected, every import declared, every dependency chosen, a hung test fails |
| `contract/` | 8 | the eight types pinned |
| `unit/` | 175 | the loop, the tools, the record, the environment check |
| `integration/` | 94 | the walkthrough, the runtime, every ending, the specimens, the live path against a scripted stand-in endpoint, the inspector's API and design rules, the phrasing dictionary, the browser checks |

Gates, all green on Windows, macOS and Ubuntu: `python -m ruff check 02_src` and `pytest`.

## Open decisions, blocking implementation

| decision | rows | blocks |
|---|---:|---|
| the trace event contract, `trace_event_contract.md` | 6 open | D-1, D-3, D-6b, and through D-6b the vertical slice (M7) and any provider work on main |
| the development catalogue, `development_catalog.md` | 7 open | D-20 to D-22; the private reserve commitment can be made now |

## Milestones, from `build_plan.md`

M0 runway, M1 the loop, M2 controlled tools: **done**. M3 multi-step investigation and M4
the structured decision: **partly**, from A's tests. M7 the vertical slice: **open** until
A is driven by the runtime with one canonical trace. M5, M6, M8, M9, M10: **not started**.
