<!-- refreshed: 2026-09-10 -->
# Architecture

**Analysis Date:** 2026-09-10

## System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                         Runtime inputs                               │
│  `IncidentContext` + provider + controlled executor                 │
│  `02_src/adii/contracts/core.py`                                    │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                         Investigator                                 │
│  model-turn loop + accumulated state + explicit budget/stop         │
│  `02_src/adii/investigator/loop.py`                                 │
│  `02_src/adii/investigator/state.py`                                │
└───────────────┬───────────────────────────────────────▲──────────────┘
                │ `ToolCall`                          │ `ToolResult`
                ▼                                     │
┌──────────────────────────────────────────────────────────────────────┐
│                     Controlled tool boundary                         │
│  injected executor today; package scaffold at `02_src/adii/tools/`  │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Terminal authorities and output                   │
│  validation: `02_src/adii/validation/` (scaffold)                   │
│  evaluation: `02_src/adii/evaluation/` (scaffold)                   │
│  reporting: `02_src/adii/reporting/render.py`                       │
└──────────────────────────────────────────────────────────────────────┘

Separate executable teaching paths:
  fixture replay: `02_src/adii/examples/walkthrough.py`
  static vision demo: `02_src/adii/demo/server.py`
```

The system is boundary-oriented rather than a conventional web application. Immutable
contracts cross explicit authority boundaries, injected collaborators isolate the
investigator from the environment, and architecture fitness tests enforce forbidden import
directions in `02_src/tests/architecture/test_boundaries.py`.

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Shared contracts | Defines the eight immutable values exchanged by all components and enforces their construction invariants | `02_src/adii/contracts/core.py` |
| Investigator loop | Requests provider turns, converts tagged responses to `ToolCall`, invokes the injected executor, accumulates `ToolResult`s, emits `TraceEvent`s, and enforces `max_turns` | `02_src/adii/investigator/loop.py` |
| Investigation state | Holds the ordered, immutable tuple of tool observations passed back to the provider | `02_src/adii/investigator/state.py` |
| Scripted provider | Supplies deterministic canned model responses and records received observations for tests | `02_src/adii/investigator/provider.py` |
| Tool boundary | Owns schemas, permissions, environment access, bounded observations, and candidate-repair rehearsal; implementation is scaffold-only | `02_src/adii/tools/README.md` |
| Independent validation | Owns clean rebuilds and `ValidationResult` verdicts without consulting investigator rehearsal; implementation is scaffold-only | `02_src/adii/validation/README.md` |
| Evaluation authority | Owns hidden truth and offline scoring, unreachable from the investigator; implementation is scaffold-only | `02_src/adii/evaluation/README.md` |
| Reporting | Renders a completed `InvestigationRun` as an honest, human-readable text report | `02_src/adii/reporting/render.py` |
| Walkthrough | Rehydrates team-visible JSON fixtures into contract objects and narrates a complete architectural flow | `02_src/adii/examples/walkthrough.py` |
| Vision demo | Serves static UI assets and five recorded JSON runs; it is an executable explanation, not runtime implementation | `02_src/adii/demo/server.py` |
| Architecture tests | Enforces import, file-I/O, private-repository, demo-isolation, and package-documentation rules | `02_src/tests/architecture/test_boundaries.py` |

## Pattern Overview

**Overall:** Boundary-oriented layered architecture with immutable data contracts and
dependency-injected ports.

**Key Characteristics:**
- Pass domain values defined in `02_src/adii/contracts/core.py`; do not invent package-local
  equivalents for incidents, calls, results, traces, decisions, validation, or runs.
- Inject provider and executor collaborators into `run()` in
  `02_src/adii/investigator/loop.py`; the investigator receives observations only as
  `ToolResult` values.
- Keep proposal, validation, and scoring as separate authorities in
  `02_src/adii/investigator/`, `02_src/adii/validation/`, and
  `02_src/adii/evaluation/`.
- Treat trace events as the observable record of behavior; reporting consumes the trace in
  `02_src/adii/reporting/render.py` rather than reconstructing investigator activity.
- Keep the fixture-backed demonstration in `02_src/adii/demo/` isolated from the real
  implementation, as enforced by `02_src/tests/architecture/test_boundaries.py`.

## Layers

**Contracts Layer:**
- Purpose: Supply the common vocabulary and reject malformed cross-boundary values.
- Location: `02_src/adii/contracts/`
- Contains: `Disposition`, `IncidentContext`, `ToolCall`, `ToolResult`, `TraceEvent`,
  `InvestigationDecision`, `ValidationResult`, and `InvestigationRun`.
- Depends on: Python standard library only, enforced by
  `02_src/tests/architecture/test_boundaries.py`.
- Used by: `02_src/adii/investigator/`, `02_src/adii/reporting/`, and
  `02_src/adii/examples/`; scaffold packages are specified to consume the same contracts in
  `02_src/adii/tools/README.md`, `02_src/adii/validation/README.md`, and
  `02_src/adii/evaluation/README.md`.

**Investigation Layer:**
- Purpose: Decide what to inspect next, preserve accumulated observations, enforce stopping,
  and emit the trace of model/tool interaction.
- Location: `02_src/adii/investigator/`
- Contains: The loop in `02_src/adii/investigator/loop.py`, immutable state in
  `02_src/adii/investigator/state.py`, and deterministic provider in
  `02_src/adii/investigator/provider.py`.
- Depends on: `02_src/adii/contracts/` plus injected provider and executor interfaces.
- Used by: Unit tests in `02_src/tests/unit/test_investigator_loop.py` and
  `02_src/tests/unit/test_investigator_provider.py`; no production end-to-end runtime entry
  point is present.

**Environment Boundary Layer:**
- Purpose: Mediate every database, filesystem, subprocess, or network observation and return
  accurate `OK`, `DENIED`, `REJECTED`, or `ERROR` results.
- Location: `02_src/adii/tools/`
- Contains: A package README and empty `__init__.py`; test-only execution behavior lives in
  `02_src/tests/unit/fakes.py`.
- Depends on: The contract layer at `02_src/adii/contracts/` when implemented.
- Used by: The injected `executor.execute(call)` port in
  `02_src/adii/investigator/loop.py:96`.

**Authority Layer:**
- Purpose: Validate candidate repairs independently and score completed runs against hidden
  truth offline.
- Location: `02_src/adii/validation/` and `02_src/adii/evaluation/`
- Contains: Package contracts in `02_src/adii/validation/README.md` and
  `02_src/adii/evaluation/README.md`; both Python packages are scaffold-only.
- Depends on: Completed contract values from `02_src/adii/contracts/core.py`.
- Used by: Reporting consumes `ValidationResult` through `InvestigationRun` in
  `02_src/adii/reporting/render.py`; the investigator is forbidden from importing either
  authority by `02_src/tests/architecture/test_boundaries.py`.

**Telemetry and Presentation Layer:**
- Purpose: Present completed runs without changing their meaning.
- Location: `02_src/adii/reporting/`
- Contains: Text rendering in `02_src/adii/reporting/render.py` and a public re-export in
  `02_src/adii/reporting/__init__.py`.
- Depends on: `02_src/adii/contracts/`.
- Used by: The walkthrough entry point in `02_src/adii/examples/walkthrough.py`.

**Orientation Layer:**
- Purpose: Teach the target architecture through recorded artifacts without claiming to be
  the implementation.
- Location: `02_src/adii/demo/` and `01_data/demo/fixtures/`
- Contains: A standard-library HTTP server, static HTML/CSS/JavaScript, and demo-schema JSON.
- Depends on: Team-visible fixtures under `01_data/demo/fixtures/`; it does not depend on the
  real contracts or investigator.
- Used by: `python -m adii.demo`, entering through `02_src/adii/demo/__main__.py`.

## Data Flow

### Implemented Investigator Request Path

1. A caller supplies `IncidentContext`, a provider, an executor, and `max_turns` to
   `run()` (`02_src/adii/investigator/loop.py:21`).
2. The loop passes the latest observation plus all accumulated observations to
   `provider.respond()` (`02_src/adii/investigator/loop.py:54`).
3. A response prefixed with `<TOOL_CALL>` is decoded into a `ToolCall` and recorded as a
   `tool_call` `TraceEvent` (`02_src/adii/investigator/loop.py:75`).
4. The injected executor handles the call and returns a `ToolResult`
   (`02_src/adii/investigator/loop.py:96`).
5. The result is recorded, appended to immutable `InvestigationState`, and supplied to the
   next provider turn (`02_src/adii/investigator/loop.py:97`).
6. An exact `<STOP>` response emits `loop_stopped` and returns the immutable trace tuple
   (`02_src/adii/investigator/loop.py:61`); exhausting the budget emits
   `budget_exceeded` and raises `TurnBudgetExceededError`
   (`02_src/adii/investigator/loop.py:39`).

The implemented loop returns `tuple[TraceEvent, ...]`; it does not construct an
`InvestigationDecision` or `InvestigationRun` in `02_src/adii/investigator/loop.py`.

### Walkthrough Fixture Replay

1. `load()` reads the team-visible walkthrough JSON files from `01_data/walkthrough/` and
   creates real contract objects (`02_src/adii/examples/walkthrough.py:30`).
2. It derives the executed-tool count from `OK` tool results and assembles an
   `InvestigationRun` (`02_src/adii/examples/walkthrough.py:56`).
3. `stages()` turns trace call/result pairs into a nine-stage boundary narrative
   (`02_src/adii/examples/walkthrough.py:64`).
4. `main()` prints the narrative and passes the completed run to `render_run()`
   (`02_src/adii/examples/walkthrough.py:122`).

This path replays a teaching fixture; it does not invoke
`02_src/adii/investigator/loop.py`, `02_src/adii/tools/`, or
`02_src/adii/validation/`.

### Vision Demo HTTP Flow

1. `python -m adii.demo` delegates to `main()` in `02_src/adii/demo/server.py` through
   `02_src/adii/demo/__main__.py:6`.
2. `ThreadingHTTPServer` serves static files from `02_src/adii/demo/web/` and API routes
   from `Handler.do_GET()` (`02_src/adii/demo/server.py:57`).
3. `/api/runs` and `/api/runs/<slug>` load JSON from
   `01_data/demo/fixtures/<slug>/run.json` (`02_src/adii/demo/server.py:35`).
4. The browser renders the recorded run; no investigator, tool execution, validator, or
   evaluator runs behind the endpoint (`02_src/adii/demo/server.py:1`).

**State Management:**
- Per-run investigator state is immutable and local to `run()` through
  `InvestigationState` in `02_src/adii/investigator/state.py`.
- The scripted provider keeps mutable cursor and received-context lists inside each
  `ScriptedProvider` instance in `02_src/adii/investigator/provider.py`.
- The demo uses module-level immutable path/order configuration in
  `02_src/adii/demo/server.py`; request data is reloaded from fixture JSON.
- No database-backed, distributed, or process-persistent application state is present under
  `02_src/adii/`.

## Key Abstractions

**Immutable Contract Values:**
- Purpose: Represent every public input, boundary exchange, verdict, and completed run.
- Examples: `02_src/adii/contracts/core.py`, re-exported by
  `02_src/adii/contracts/__init__.py`.
- Pattern: Frozen dataclasses plus `Disposition` as a `StrEnum`; invariants execute in
  `__post_init__`.

**Provider Port:**
- Purpose: Produce the next textual investigator response from the latest and accumulated
  tool observations.
- Examples: `ScriptedProvider.respond()` in `02_src/adii/investigator/provider.py` and
  `StateAwareFakeProvider.respond()` in `02_src/tests/unit/fakes.py`.
- Pattern: Structural/duck-typed dependency injection; there is no explicit protocol or
  abstract base class.

**Executor Port:**
- Purpose: Turn a `ToolCall` into one `ToolResult` without granting the investigator direct
  environment access.
- Examples: Invocation in `02_src/adii/investigator/loop.py:96` and test implementation in
  `02_src/tests/unit/fakes.py:7`.
- Pattern: Structural/duck-typed dependency injection through an `execute(call)` method.

**Trace:**
- Purpose: Preserve ordered evidence of investigator activity and stopping/budget behavior.
- Examples: `TraceEvent` in `02_src/adii/contracts/core.py` and emission sites in
  `02_src/adii/investigator/loop.py`.
- Pattern: Append-only list during execution, returned as an immutable tuple; sequence is
  derived from the current list length.

**Independent Verdict:**
- Purpose: Keep repair acceptance outside the actor that proposed the repair.
- Examples: `ValidationResult` and the validation requirement on `InvestigationRun` in
  `02_src/adii/contracts/core.py`; authority definition in
  `02_src/adii/validation/README.md`.
- Pattern: A REPAIR run must include exactly one independent result; non-REPAIR runs must
  not include one.

## Entry Points

**Investigator API:**
- Location: `02_src/adii/investigator/loop.py`
- Triggers: Direct Python call to `run(incident, provider, executor, max_turns=...)`.
- Responsibilities: Drive turns, tool round trips, observation accumulation, tracing, stop,
  and turn-budget enforcement.

**Walkthrough CLI:**
- Location: `02_src/adii/examples/walkthrough.py`
- Triggers: `python -m adii.examples.walkthrough [--step] [--report-only]`.
- Responsibilities: Load `01_data/walkthrough/`, narrate boundary crossings, and render a
  completed fixture run.

**Demo CLI and HTTP Server:**
- Location: `02_src/adii/demo/__main__.py` and `02_src/adii/demo/server.py`
- Triggers: `python -m adii.demo <port>` (port argument optional).
- Responsibilities: Listen on `127.0.0.1`, serve `02_src/adii/demo/web/`, and expose recorded
  fixture endpoints backed by `01_data/demo/fixtures/`.

**Environment Check:**
- Location: `02_src/scripts/check_env.py`
- Triggers: `python 02_src/scripts/check_env.py`.
- Responsibilities: Verify Python 3.12, package importability, pytest, and Ruff availability.

**Generated Documentation Scripts:**
- Location: `02_src/scripts/sync_briefing.py` and `02_src/scripts/sync_status.py`
- Triggers: Direct `python` module-file invocation and CI in `.github/workflows/ci.yml`.
- Responsibilities: Keep `AGENTS.md`/`CLAUDE.md` synchronized with
  `02_src/docs/agent_briefing.md` and keep `02_src/docs/current_status.md` derived from code
  and `02_src/docs/build_plan.md`.

## Architectural Constraints

- **Threading:** `02_src/adii/investigator/loop.py` is synchronous and single-threaded;
  `02_src/adii/demo/server.py` handles HTTP requests with the standard-library
  `ThreadingHTTPServer`.
- **Global state:** `STOP_SIGNAL` and `TOOL_CALL_PREFIX` are module constants in
  `02_src/adii/investigator/loop.py`; `HERE`, `REPO`, `FIXTURES`, `WEB`, and `ORDER` are
  module constants in `02_src/adii/demo/server.py`. Mutable runtime state stays on provider
  instances or inside a `run()` call.
- **Circular imports:** Not detected in `02_src/adii/`; contracts depend only on the standard
  library, investigator imports contracts, reporting imports contracts, and examples import
  contracts/reporting.
- **World access:** Keep filesystem, database, subprocess, and network access outside the
  investigator and behind `02_src/adii/tools/`; the test exceptions for direct external
  access are explicitly listed in `02_src/tests/architecture/test_boundaries.py`.
- **Authority direction:** Never import `02_src/adii/validation/` or
  `02_src/adii/evaluation/` from `02_src/adii/investigator/`; the investigator hands over a
  decision and cannot inspect how it is judged.
- **Demo isolation:** Do not import `02_src/adii/demo/` from implementation packages;
  `02_src/tests/architecture/test_boundaries.py` treats the demo as explanation only.
- **Contract stability:** Do not change `02_src/adii/contracts/` as a local refactor; its
  values are shared across every boundary and require cross-boundary human review under
  `AGENTS.md`.
- **No private runtime dependencies:** Do not import prior private packages; inherited
  requirements live only in `02_src/docs/inherited/` and are enforced by
  `02_src/tests/architecture/test_boundaries.py`.
- **Cross-platform execution:** Use Python module/file entry points, not shell scripts,
  Docker, Make, or machine-specific infrastructure; CI runs Windows, macOS, and Ubuntu via
  `.github/workflows/ci.yml`.

## Anti-Patterns

### Using Demo Fixtures as Runtime Implementation

**What happens:** The demo presents complete recorded runs from
`01_data/demo/fixtures/`, but no non-demo implementation imports them.
**Why it's wrong:** Importing `02_src/adii/demo/` or its fixture shape into runtime code
would replace real investigation and independent authority with curated presentation data;
`02_src/adii/demo/CONTRACT.md` explicitly says its schema is not the team contract.
**Do this instead:** Implement runtime behavior in the corresponding package under
`02_src/adii/` and exchange values from `02_src/adii/contracts/core.py`; keep the demo
isolated as enforced by `02_src/tests/architecture/test_boundaries.py`.

### Letting the Investigator Reach Around the Tool Boundary

**What happens:** No direct file/database/network access is detected in
`02_src/adii/investigator/`; calls leave through the injected executor in
`02_src/adii/investigator/loop.py:96`.
**Why it's wrong:** Direct access lets agent-facing code bypass refusal, permissions, result
bounds, and hidden-evaluation isolation.
**Do this instead:** Add environment integrations only under `02_src/adii/tools/`, expose
them through `ToolCall`/`ToolResult`, and preserve the fitness checks in
`02_src/tests/architecture/test_boundaries.py`.

### Treating Rehearsal as Validation

**What happens:** `InvestigationDecision` carries a candidate patch, while
`ValidationResult` is a separate value in `02_src/adii/contracts/core.py`; no implemented
validator exists in `02_src/adii/validation/`.
**Why it's wrong:** An investigator-controlled sandbox can confirm a repair against its own
assumptions and cannot issue an independent verdict.
**Do this instead:** Build verdict logic only under `02_src/adii/validation/`, reconstruct
from frozen inputs, and attach its `ValidationResult` to the completed run outside the
investigator.

## Error Handling

**Strategy:** Reject invalid public values at construction, represent controlled tool
outcomes as data, and reserve named exceptions for invalid API configuration or hard loop
bounds.

**Patterns:**
- Contract dataclasses raise `ValueError` from `__post_init__` for malformed dispositions,
  status values, empty identifiers, invalid repair combinations, or negative counters in
  `02_src/adii/contracts/core.py`.
- `run()` rejects boolean, non-integer, or negative `max_turns` before starting and raises
  `TurnBudgetExceededError` with the trace that proves the bound event in
  `02_src/adii/investigator/loop.py`.
- The tool protocol uses `ToolResult.status` values `OK`, `DENIED`, `REJECTED`, and `ERROR`;
  the loop records and feeds every result back rather than raising for controlled outcomes
  in `02_src/adii/investigator/loop.py`.
- Script exhaustion raises the named `ScriptExhaustedError` in
  `02_src/adii/investigator/provider.py`.
- Malformed tagged tool-call JSON currently propagates `json.JSONDecodeError` from
  `02_src/adii/investigator/loop.py`, as pinned by
  `02_src/tests/unit/test_investigator_loop.py`.
- Demo HTTP routing returns JSON 404 responses for unknown endpoints, slugs, and sections in
  `02_src/adii/demo/server.py`.

## Cross-Cutting Concerns

**Logging:** Runtime observability is modeled as ordered `TraceEvent` values in
`02_src/adii/contracts/core.py` and emitted by `02_src/adii/investigator/loop.py`; the demo
server uses console request logging in `02_src/adii/demo/server.py`.

**Validation:** Data-shape invariants live in frozen contracts at
`02_src/adii/contracts/core.py`; candidate-repair verdict logic belongs exclusively in the
scaffold package `02_src/adii/validation/` and must rebuild from frozen inputs.

**Authentication:** Not applicable. The implemented runtime uses no network provider, the
demo binds locally at `127.0.0.1` in `02_src/adii/demo/server.py`, and no authentication
layer exists under `02_src/adii/`.

---

*Architecture analysis: 2026-09-10*
