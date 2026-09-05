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
| Examples | `02_src/adii/examples/` | the runnable walkthrough |
| Demo | `02_src/adii/demo/` | the vision demo: recorded runs, served |
| Demo data | `01_data/demo/` | the team-visible world and the recorded runs |

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

**CALLED BY** The runtime that runs an incident end to end.

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

## demo/

**PURPOSE** The orientation layer. Five recorded runs served through one interface, so the
shape of a decision can be argued about before the system that produces one exists.

**INPUT** The recorded runs in `01_data/demo/fixtures/`.

**OUTPUT** A local web page. No model, no database, no agent.

**CALLS** The standard library only, so it runs on a laptop with nothing installed.

**CALLED BY** `python -m adii.demo`. Nothing in the implementation.

**MUST NOT DO** Be imported by any other `adii` package. It has fixture data where the real
system has an agent, a tool layer and a validator; one import and it stops being a demo and
starts being the codebase.
*Enforced by* `test_the_demo_is_never_imported_by_the_implementation`,
`test_the_demo_backend_stays_dependency_free`.
