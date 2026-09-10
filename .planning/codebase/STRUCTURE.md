# Codebase Structure

**Analysis Date:** 2026-09-10

## Directory Layout

```text
Project SDA/
├── 01_data/                         # Team-visible runtime and teaching data
│   ├── demo/
│   │   ├── fixtures/                # Five recorded vision-demo runs
│   │   └── world/                   # Canonical world work order; no implementation data
│   └── walkthrough/                 # One narrated contract-level fixture run
├── 02_src/                          # Shippable Python source, tests, scripts, and docs
│   ├── adii/
│   │   ├── contracts/               # Shared immutable vocabulary
│   │   ├── investigator/            # Loop, state, and deterministic provider
│   │   ├── tools/                   # Controlled environment boundary; scaffold
│   │   ├── validation/              # Independent repair verdict; scaffold
│   │   ├── evaluation/              # Hidden-truth scoring authority; scaffold
│   │   ├── reporting/               # Human-readable run rendering
│   │   ├── examples/                # Runnable walkthrough
│   │   └── demo/                    # Isolated fixture-backed HTTP orientation layer
│   ├── tests/
│   │   ├── architecture/            # Executable repository and authority boundaries
│   │   ├── contract/                # Shared-value invariant tests
│   │   ├── integration/             # Walkthrough and front-door data checks
│   │   └── unit/                    # Investigator/provider/environment unit tests
│   ├── scripts/                     # Cross-platform Python maintenance commands
│   └── docs/                        # Architecture, plans, status, glossary, inherited rules
├── 03_assets/                       # Presentation-only visual material
│   ├── design/                      # Historical prototypes
│   ├── diagrams/                    # Exported architecture/decision visuals
│   └── screenshots/                 # Demo and run captures
├── .claude/skills/adii-change/      # Repository-specific change procedure
├── .github/workflows/               # Cross-platform CI
├── .planning/codebase/              # Generated GSD codebase maps
├── AGENTS.md                         # Codex briefing generated from source docs
├── CLAUDE.md                         # Claude briefing generated from source docs
├── README.md                         # Project front door and quick start
├── TEAM.md                           # Team workflow
├── pyproject.toml                    # Package, pytest, and Ruff configuration
└── requirements.txt                 # Pinned install set
```

## Directory Purposes

**`01_data/`:**
- Purpose: Store only team-visible data required to run or teach the system.
- Contains: Demo fixtures under `01_data/demo/fixtures/`, a not-yet-built operational world
  specification at `01_data/demo/world/README.md`, and walkthrough JSON/text under
  `01_data/walkthrough/`.
- Key files: `01_data/README.md`, `01_data/walkthrough/README.md`, and
  `01_data/demo/world/README.md`.
- Placement rule: Never place answer keys, frozen evaluation worlds, or hidden authority
  state here; the disclosure boundary is documented in `01_data/README.md` and checked by
  `02_src/tests/integration/test_front_door_invariants.py`.

**`02_src/adii/contracts/`:**
- Purpose: Define the shared machine-readable vocabulary for all component boundaries.
- Contains: One `StrEnum`, seven frozen dataclasses, construction invariants, and public
  re-exports.
- Key files: `02_src/adii/contracts/core.py`, `02_src/adii/contracts/__init__.py`, and
  `02_src/adii/contracts/README.md`.
- Placement rule: Keep the package standard-library-only and behavior-free; contract edits
  require cross-boundary human review under `AGENTS.md`.

**`02_src/adii/investigator/`:**
- Purpose: Own the model-turn loop, investigation state, tool-call requests, budgets, and
  stopping.
- Contains: `run()` and loop errors, `InvestigationState`, and `ScriptedProvider`.
- Key files: `02_src/adii/investigator/loop.py`,
  `02_src/adii/investigator/state.py`,
  `02_src/adii/investigator/provider.py`, and
  `02_src/adii/investigator/README.md`.
- Placement rule: Do not add direct I/O or imports of `adii.validation` or
  `adii.evaluation`; use injected collaborators and contract values.

**`02_src/adii/tools/`:**
- Purpose: Be the sole controlled gateway to filesystem, database, subprocess, and network
  observations for the investigator.
- Contains: `02_src/adii/tools/README.md` and a scaffold `__init__.py`; no executor
  implementation exists in this package.
- Key files: `02_src/adii/tools/README.md` and `02_src/adii/tools/__init__.py`.
- Placement rule: Put real tool schemas, dispatch, permissions, result bounding, and
  environment adapters here; never accept arbitrary filesystem paths as tool arguments.

**`02_src/adii/validation/`:**
- Purpose: Independently accept or reject candidate repairs by rebuilding from frozen
  inputs.
- Contains: `02_src/adii/validation/README.md` and a scaffold `__init__.py`.
- Key files: `02_src/adii/validation/README.md` and
  `02_src/adii/validation/__init__.py`.
- Placement rule: Put deterministic repair-verdict logic here, outside the investigator;
  do not consult agent rehearsal output or evaluation answer keys.

**`02_src/adii/evaluation/`:**
- Purpose: Own offline scoring, hidden truth, baseline arms, and answer-key authority.
- Contains: `02_src/adii/evaluation/README.md` and a scaffold `__init__.py`.
- Key files: `02_src/adii/evaluation/README.md` and
  `02_src/adii/evaluation/__init__.py`.
- Placement rule: Keep scoring and answer keys unreachable from
  `02_src/adii/investigator/`; frozen materials are additive and hash-bound rather than
  edited.

**`02_src/adii/reporting/`:**
- Purpose: Render traces, decisions, independent verdicts, and measured run usage for
  people.
- Contains: Text report logic and its public package re-export.
- Key files: `02_src/adii/reporting/render.py`,
  `02_src/adii/reporting/__init__.py`, and
  `02_src/adii/reporting/README.md`.
- Placement rule: Add presentation and telemetry behavior here without changing the meaning
  of contract values; derive counters from trace data.

**`02_src/adii/examples/`:**
- Purpose: Provide executable, non-scientific teaching examples over real contract objects.
- Contains: The fixture-loading and narrated CLI walkthrough.
- Key files: `02_src/adii/examples/walkthrough.py` and
  `02_src/adii/examples/__init__.py`.
- Placement rule: Keep examples explicit about fixture status; external access is acceptable
  here for teaching input, but examples are not production authority implementations.

**`02_src/adii/demo/`:**
- Purpose: Show the eventual system shape through a local fixture-backed browser experience.
- Contains: Standard-library server code, static assets under `02_src/adii/demo/web/`, and
  the non-authoritative demo schema.
- Key files: `02_src/adii/demo/__main__.py`, `02_src/adii/demo/server.py`,
  `02_src/adii/demo/CONTRACT.md`, and `02_src/adii/demo/README.md`.
- Placement rule: Keep this directory dependency-free and isolated; runtime packages must
  not import it, as enforced by `02_src/tests/architecture/test_boundaries.py`.

**`02_src/tests/`:**
- Purpose: Pin behavior, shared contracts, integration flows, and architectural authority
  boundaries.
- Contains: `architecture/`, `contract/`, `integration/`, and `unit/` suites.
- Key files: `02_src/tests/architecture/test_boundaries.py`,
  `02_src/tests/contract/test_contracts.py`,
  `02_src/tests/integration/test_walkthrough.py`, and
  `02_src/tests/unit/test_investigator_loop.py`.
- Placement rule: Match the test directory to the kind of guarantee; keep deterministic
  collaborators in `02_src/tests/unit/fakes.py`.

**`02_src/scripts/`:**
- Purpose: Provide cross-platform environment and documentation maintenance commands.
- Contains: Environment checking and generated-file synchronization scripts.
- Key files: `02_src/scripts/check_env.py`, `02_src/scripts/sync_briefing.py`, and
  `02_src/scripts/sync_status.py`.
- Placement rule: Add portable Python commands here and invoke them with `python`; do not
  add shell scripts.

**`02_src/docs/`:**
- Purpose: Hold technical architecture, build status, domain definitions, review process,
  and transferred requirements.
- Contains: `02_src/docs/architecture.md`, `02_src/docs/system_map.md`,
  `02_src/docs/build_plan.md`, generated `02_src/docs/current_status.md`, and audited prior
  requirements under `02_src/docs/inherited/`.
- Key files: `02_src/docs/agent_briefing.md`,
  `02_src/docs/inherited/CONFORMANCE.md`, and `02_src/docs/DATA_WORLD_v0.md`.
- Placement rule: Edit source-of-truth files rather than generated
  `02_src/docs/current_status.md`, `AGENTS.md`, or `CLAUDE.md` directly.

**`03_assets/`:**
- Purpose: Store presentation material that the software does not need to run.
- Contains: Historical designs, diagrams, and screenshots.
- Key files: `03_assets/README.md`.
- Placement rule: Keep required runtime assets out of this directory; exported diagrams
  belong in `03_assets/diagrams/` and UI history belongs in `03_assets/design/`.

## Key File Locations

**Entry Points:**
- `02_src/adii/investigator/loop.py`: Python API for the implemented investigator loop.
- `02_src/adii/examples/walkthrough.py`: `python -m adii.examples.walkthrough` teaching CLI.
- `02_src/adii/demo/__main__.py`: `python -m adii.demo` package entry point.
- `02_src/adii/demo/server.py`: Local HTTP server and recorded-run API.
- `02_src/scripts/check_env.py`: Development-machine readiness check.

**Configuration:**
- `pyproject.toml`: Build backend, package metadata, Python 3.12 constraint, pytest paths,
  and Ruff rules.
- `requirements.txt`: Reproducible installation dependencies used by contributors and CI.
- `.github/workflows/ci.yml`: Windows, macOS, and Ubuntu verification pipeline.
- `AGENTS.md`: Auto-loaded repository constraints for coding agents.
- `.claude/skills/adii-change/SKILL.md`: Project change workflow and boundary reminders.

**Core Logic:**
- `02_src/adii/contracts/core.py`: Cross-boundary domain model and invariants.
- `02_src/adii/investigator/loop.py`: Turn/tool loop and trace emission.
- `02_src/adii/investigator/state.py`: Accumulated investigation observations.
- `02_src/adii/investigator/provider.py`: Deterministic scripted model substitute.
- `02_src/adii/reporting/render.py`: Completed-run text rendering.

**Testing:**
- `02_src/tests/architecture/test_boundaries.py`: Authority and dependency fitness tests.
- `02_src/tests/contract/test_contracts.py`: Contract construction/invariant tests.
- `02_src/tests/unit/test_investigator_loop.py`: Loop, budget, trace, result-status, and state
  tests.
- `02_src/tests/unit/test_investigator_provider.py`: Scripted provider tests.
- `02_src/tests/unit/fakes.py`: Deterministic provider/executor test collaborators.
- `02_src/tests/integration/test_walkthrough.py`: Fixture replay and report integration.
- `02_src/tests/integration/test_front_door_invariants.py`: Data disclosure and demo-fixture
  invariants.

**Project Understanding:**
- `README.md`: Setup, commands, repository map, and contributor reading order.
- `02_src/docs/system_map.md`: Concept-to-package ownership and dependency direction.
- `02_src/docs/architecture.md`: Authority-boundary rationale.
- `02_src/docs/current_status.md`: Generated inventory of implemented versus scaffold code.
- `02_src/docs/build_plan.md`: Milestone source of truth.
- `02_src/docs/glossary.md`: Domain terminology.

## Naming Conventions

**Files:**
- Use lowercase `snake_case.py` for Python modules, as in
  `02_src/adii/investigator/provider.py` and `02_src/scripts/sync_status.py`.
- Name tests `test_<subject>.py`, as in
  `02_src/tests/unit/test_investigator_loop.py` and
  `02_src/tests/architecture/test_boundaries.py`.
- Use `README.md` as each package/directory briefing, as in
  `02_src/adii/investigator/README.md` and `01_data/README.md`.
- Use uppercase Markdown names for authority/specification artifacts when the name is a
  project-level contract, as in `02_src/adii/demo/CONTRACT.md` and
  `02_src/docs/inherited/CONFORMANCE.md`.
- Use lowercase descriptive names for ordinary technical documentation, as in
  `02_src/docs/system_map.md` and `02_src/docs/build_plan.md`.
- Name demo fixture directories with lowercase kebab-case slugs, as in
  `01_data/demo/fixtures/repair-accepted/` and
  `01_data/demo/fixtures/no-repair/`.

**Directories:**
- Use the numbered submission roots `01_data/`, `02_src/`, and `03_assets/`; preserve these
  names because packaging relies on them as documented in `README.md`.
- Use lowercase package/capability names under `02_src/adii/`, such as
  `02_src/adii/investigator/`, `02_src/adii/validation/`, and
  `02_src/adii/reporting/`.
- Organize tests by guarantee type under `02_src/tests/architecture/`,
  `02_src/tests/contract/`, `02_src/tests/integration/`, and `02_src/tests/unit/`.
- Treat capability directories as system organization, not individual ownership; this rule
  is stated in `AGENTS.md` and `02_src/docs/build_plan.md`.

## Where to Add New Code

**New Investigator Behavior:**
- Primary code: `02_src/adii/investigator/`
- Tests: `02_src/tests/unit/test_investigator_loop.py` for loop behavior or a new focused
  `02_src/tests/unit/test_<subject>.py`.
- Boundary checks: Extend `02_src/tests/architecture/test_boundaries.py` only to make a
  stated boundary executable, not to weaken an existing restriction.

**New Controlled Tool:**
- Primary code: `02_src/adii/tools/`
- Tests: Add focused unit coverage under `02_src/tests/unit/` and cross-layer behavior under
  `02_src/tests/integration/`.
- Contract usage: Return `ToolResult` from `02_src/adii/contracts/core.py`; keep schemas,
  dispatch, permission checks, and environment access inside `02_src/adii/tools/`.

**New Validator:**
- Primary code: `02_src/adii/validation/`
- Tests: Add deterministic validator tests under `02_src/tests/unit/` and clean-rebuild
  integration coverage under `02_src/tests/integration/`.
- Boundary rule: Consume an `InvestigationDecision` and return `ValidationResult` values
  defined in `02_src/adii/contracts/core.py`; never place verdict logic in
  `02_src/adii/investigator/`.

**New Evaluator or Scorer:**
- Primary code: `02_src/adii/evaluation/`
- Tests: Add scorer tests under `02_src/tests/unit/` plus authority-isolation checks in
  `02_src/tests/architecture/`.
- Hidden material: Keep answer keys out of team-visible `01_data/`; the disclosure tests in
  `02_src/tests/integration/test_front_door_invariants.py` protect this boundary.

**New Reporting Output:**
- Primary code: `02_src/adii/reporting/`
- Tests: Add unit tests under `02_src/tests/unit/` and end-to-end rendering assertions under
  `02_src/tests/integration/`.
- Public API: Re-export stable public helpers from
  `02_src/adii/reporting/__init__.py`, following the existing `render_run` pattern.

**New Runnable Example:**
- Implementation: `02_src/adii/examples/<example_name>.py`
- Team-visible fixtures: `01_data/<example_name>/`
- Tests: `02_src/tests/integration/test_<example_name>.py`
- Entry convention: Include an explicit `main(argv=None) -> int` and a
  `raise SystemExit(main())` guard, following
  `02_src/adii/examples/walkthrough.py`.

**New Demo UI or Recorded Run:**
- Static UI: `02_src/adii/demo/web/`
- Demo server behavior: `02_src/adii/demo/server.py`
- Recorded fixture: `01_data/demo/fixtures/<kebab-case-slug>/run.json`
- Tests: `02_src/tests/integration/test_front_door_invariants.py`
- Isolation rule: Do not use demo fixture or presentation fields as real runtime contracts;
  `02_src/adii/demo/CONTRACT.md` is explicitly non-authoritative.

**Utilities:**
- Shared domain vocabulary: Use `02_src/adii/contracts/`; do not add behavior-heavy helpers
  there.
- Capability-local helpers: Keep them beside their owning module under the relevant
  `02_src/adii/<capability>/` package.
- Repository maintenance commands: Add portable Python modules to `02_src/scripts/` and
  invoke them as `python 02_src/scripts/<name>.py`.
- Avoid a generic utility dumping ground: no `utils/` directory exists under
  `02_src/adii/`; place code by capability and boundary.

## Special Directories

**`02_src/docs/inherited/`:**
- Purpose: Preserve audited defects and lifecycle/control lessons transferred from a private
  predecessor without importing its code or claiming its results.
- Generated: No.
- Committed: Yes.
- Constraint: Treat `02_src/docs/inherited/CONFORMANCE.md` as requirements and preserve the
  prior-art attribution enforced by `02_src/tests/architecture/test_boundaries.py`.

**`01_data/demo/fixtures/`:**
- Purpose: Back the isolated orientation demo with five complete recorded runs.
- Generated: No; current files declare demo fixture provenance and are presentation data.
- Committed: Yes.
- Constraint: These fixtures carry no evaluation claim and must not become runtime
  implementation inputs outside `02_src/adii/demo/`.

**`01_data/demo/world/`:**
- Purpose: Reserve the location and work order for the canonical executable demo world.
- Generated: No.
- Committed: Yes; only `01_data/demo/world/README.md` is present.
- Constraint: Keep hidden truth outside team-visible `01_data/` even when operational inputs
  are added.

**`02_src/adii/demo/web/`:**
- Purpose: Hold browser assets served by `02_src/adii/demo/server.py`.
- Generated: No.
- Committed: Yes.
- Constraint: Treat the files as orientation UI, not application runtime modules.

**`02_src/docs/current_status.md`:**
- Purpose: Report milestones and implemented package line counts from repository state.
- Generated: Yes, by `02_src/scripts/sync_status.py`.
- Committed: Yes.
- Constraint: Change `02_src/docs/build_plan.md` or implementation files, then regenerate;
  never maintain this file manually.

**`AGENTS.md` and `CLAUDE.md`:**
- Purpose: Present the same auto-loaded coding-agent briefing to different assistants.
- Generated: Yes, from `02_src/docs/agent_briefing.md` by
  `02_src/scripts/sync_briefing.py`.
- Committed: Yes.
- Constraint: Edit `02_src/docs/agent_briefing.md`, regenerate, and let
  `02_src/tests/architecture/test_briefing_is_current.py` verify synchronization.

**`.planning/codebase/`:**
- Purpose: Hold GSD-generated reference maps for planning and execution.
- Generated: Yes.
- Committed: Determined by the GSD orchestrator; these files are planning artifacts rather
  than runtime inputs.

**`.github/workflows/`:**
- Purpose: Verify environment, lint, architecture boundaries, generated docs, tests, and the
  walkthrough across Windows, macOS, and Ubuntu.
- Generated: No.
- Committed: Yes.
- Key file: `.github/workflows/ci.yml`.

**`03_assets/design/`:**
- Purpose: Preserve design exploration history.
- Generated: No.
- Committed: Yes.
- Constraint: Nothing under `02_src/` imports this directory, and runtime correctness must
  not depend on it, per `03_assets/README.md`.

---

*Structure analysis: 2026-09-10*
