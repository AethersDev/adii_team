# ADII system map

What you are looking at, and where each idea lives in the code. Read this second, after
the README's Quick Start and before touching anything.

`architecture.md` argues *why* the boundaries are where they are. This file just tells you
*what is where*.

## The flow

```text
Incident
   │
   ▼
Investigator ─────────────┐
   │                      │  decides what to look at next
   ▼                      │
Controlled tool call      │
   │                      │
   ▼                      │
Observation               │
   │                      │
   ▼                      │
Evidence / investigation state
   │                      │
   ├── continue ──────────┘
   │
   ▼  stop
Structured decision
   ├── REPAIR ── carries a candidate action
   ├── NO_REPAIR
   └── ESCALATE
          │
          ▼
   Independent validation
          │
          ▼
      ACCEPT / REJECT
          │
          ▼
   Reporting  ·  Evaluation
```

Two things in that picture are easy to miss and both are the point.

The loop back from *investigation state* to *investigator* is what makes ADII an
investigator rather than a classifier: it decides what to look at next based on what it
just saw. And validation sits **after** the decision and is **not** part of it — the thing
that proposes a repair never gets to say whether the repair was accepted.

## Concept to code

| Concept | Code | Responsibility |
|---|---|---|
| Contracts | `02_src/adii/contracts/` | the shared machine-readable interfaces every other package speaks |
| Investigator | `02_src/adii/investigator/` | agent loop, investigation state, stopping, the terminal decision |
| Tools | `02_src/adii/tools/` | controlled access to the environment; observations and evidence |
| Validation | `02_src/adii/validation/` | independent acceptance of a candidate action |
| Evaluation | `02_src/adii/evaluation/` | scoring against hidden truth; kept away from the investigator |
| Reporting | `02_src/adii/reporting/` | traces, run artifacts, human-readable output |
| Runtime | `02_src/adii/runtime/` | one incident end to end: investigator, validation, archive, report |
| Examples | `02_src/adii/examples/` | the runnable walkthrough, and one produced record per ending |
| The page | `02_src/adii/demo/` | ADII's one page: investigate (against a local model, when the operator allows it), watch, read the archive, answer |
| Run archive | `01_data/runs/` | one record per run, what the inspector reads |
| Design system | `03_assets/identity/` | the identity handoff; the inspector's stylesheet is a synced copy of its `css/` |
| Demo data | `01_data/demo/` | the team-visible operational world (a work order today) |

`current_status.md` says which of these are built and which are still scaffolds. It is
generated, so it does not go stale.

---

## contracts/

**PURPOSE** The vocabulary every other package speaks. Eight types: `Disposition`,
`IncidentContext`, `ToolCall`, `ToolResult`, `TraceEvent`, `InvestigationDecision`,
`ValidationResult`, `InvestigationRun`.

**INPUT** Nothing. It is definitions.

**OUTPUT** Frozen dataclasses and one `StrEnum`.

**CALLS** The standard library, and only the standard library.

**CALLED BY** Everything.

**MUST NOT DO** Import any third-party package, or any other `adii` package. A dependency
here becomes everybody's dependency.
*Enforced by* `test_contracts_depend_on_nothing_but_the_standard_library`.

---

## investigator/

**PURPOSE** The agent. Decides what to look at, asks for it through tools, decides when it
has seen enough, and commits to one disposition.

**INPUT** An `IncidentContext` and the `ToolResult`s it receives back.

**OUTPUT** `ToolCall`s while investigating; one `InvestigationDecision` at the end.

**CALLS** `contracts/`, and the tool layer.

**CALLED BY** Its own tests today, over the real tool layer. The runtime will call it
through an adapter once the trace event contract is decided; until then the runtime
drives a scripted stand-in.

**MUST NOT DO**
- Read the filesystem, a database, a subprocess or the network directly. Everything it
  sees comes back through a tool that was allowed to refuse.
- Import `validation/` or `evaluation/`. The contestant does not get to see the judge.
*Enforced by* `test_the_investigator_and_contracts_do_no_file_io`,
`test_only_the_tool_layer_touches_the_outside_world`,
`test_the_investigator_cannot_reach_the_judge`.

---

## tools/

**PURPOSE** The investigator's entire view of the world, and the thing that stops it seeing
too much. Schemas, SQL, permissions, the candidate-repair sandbox.

**INPUT** A `ToolCall`.

**OUTPUT** A `ToolResult` carrying a status — including `DENIED`, which is a successful
outcome, not a failure.

**CALLS** The outside world. This is the only package allowed to.

**CALLED BY** The investigator.

**MUST NOT DO** Return raw environment access, or silently widen what a caller asked for.
A tool that cannot say no is not a boundary.
*Enforced by* `test_only_the_tool_layer_touches_the_outside_world`.

---

## validation/

**PURPOSE** Independently decide whether a candidate action is acceptable. The other
authority.

**INPUT** A candidate action plus validation-visible state.

**OUTPUT** A `ValidationResult` — `ACCEPT` or `REJECT`, with reasons.

**CALLS** Deterministic validation code. No model.

**CALLED BY** The runtime, after the investigator has proposed something.

**MUST NOT DO**
- Ask the investigator whether its own repair was correct, or trust a sandbox result the
  investigator reports about itself.
- Read evaluation answer keys.
- Become part of the model's reasoning loop.

---

## evaluation/

**PURPOSE** Whether the answer was right, and how we know that independently of the thing
that produced it. Incidents, answer keys, scoring, baselines.

**INPUT** A completed `InvestigationRun`, and the hidden truth for that incident.

**OUTPUT** Scores and comparisons against baselines.

**CALLS** `contracts/`, and its own frozen data.

**CALLED BY** Offline analysis. Never the runtime path an investigation takes.

**MUST NOT DO** Appear in agent context, or be importable from `investigator/`. An
investigator that can read the answer has not investigated anything.
*Enforced by* `test_the_investigator_cannot_reach_the_judge`.

**Not the same thing as validation.** Validation asks *can this action be accepted?*
Evaluation asks *how did the investigator score against hidden truth?* Different trust
domains, different data, different times.

---

## reporting/

**PURPOSE** Make a run understandable. Traces, run artifacts, cost and latency, the
human-readable report.

**INPUT** An `InvestigationRun` and its `TraceEvent`s.

**OUTPUT** Rendered reports and persisted run artifacts.

**CALLS** `contracts/`.

**CALLED BY** The runtime, and anyone reading a past run.

**MUST NOT DO** Take a component's word for its own numbers. Counters come from the trace,
never from a self-report. If a behaviour is not in the trace, nobody can prove it happened.

---

## runtime/

**PURPOSE** One incident, end to end, in one process: the investigator, then validation
if a repair was proposed, then the record, the archive and the report.

**INPUT** An incident id and a provider. `scripted` replays the investigator and the validator
from the walkthrough's recorded run, over the real tool layer, and costs nothing.

**OUTPUT** One `record.json` in `01_data/runs/` for every way the run ended — a submission,
a run the loop ended, a failure of ours — and the rendered report when there was a decision.

**CALLS** The investigator, the tool layer and the validator through three protocols, and
`reporting/` for the record. It is the only component that sees every boundary crossing,
so it writes the trace itself, on the way through.

**CALLED BY** `python -m adii.runtime`.

**MUST NOT DO** Take a component's word for a counter, or let anything but a REPAIR reach
the validator. If a behaviour is not in the trace it writes, it did not happen.

---

## demo/

**PURPOSE** ADII's one page. Every archived run, served to a browser: the
trace, the decision, the verdict, the cost, and where the record came from.

**INPUT** The run archive in `01_data/runs/`, one `record.json` per run.

**OUTPUT** A local web page. Read-only by default: no model, no database, no agent in this
process. Started with `--model`, it also starts runs — the runtime, in this process, against
a local endpoint only, one at a time — and the page watches them through the live trace.

**CALLS** The standard library; `reporting/` to read records; `runtime/` to start a run when
the operator allowed it. Its stylesheet is the
identity handoff's, copied from `03_assets/identity/css/` by `scripts/sync_identity.py`
and held byte-identical by a test.

**CALLED BY** `python -m adii.demo`. Nothing in the implementation.

**MUST NOT DO** Be imported by any other `adii` package, launch a run against anything but
a local model the operator configured when starting the server (rule 12 of the design
system, amended in writing on 16 September 2026), or invent a field that is not in the
record. A page that can reach a paid provider can spend money; a page that fills in a blank
is asserting something the runtime never said.
*Enforced by* `test_the_demo_is_never_imported_by_the_implementation`,
`test_the_demo_backend_stays_dependency_free`.
