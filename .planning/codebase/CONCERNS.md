# Codebase Concerns

**Analysis Date:** 2026-09-10

## Tech Debt

**The executable system is still mostly a contract, fixture, and fake-provider skeleton:**
- Issue: The only runtime implementation is a minimal investigator loop; `tools`, `validation`, and `evaluation` contain package documentation and empty `__init__.py` files. The walkthrough constructs a completed run directly from committed fixture JSON rather than exercising those authorities.
- Files: `02_src/adii/investigator/loop.py`, `02_src/adii/tools/__init__.py`, `02_src/adii/validation/__init__.py`, `02_src/adii/evaluation/__init__.py`, `02_src/adii/examples/walkthrough.py`, `01_data/walkthrough/`
- Impact: Passing walkthrough and demo tests do not establish that ADII can investigate, validate, score, or archive a real incident. Most boundary failures remain impossible to observe end to end.
- Fix approach: Build the roadmap as vertical slices: controlled tool execution, structured terminal decision, independent validation, run persistence, then offline evaluation. Keep the fake provider as a deterministic integration path.

**The model protocol is encoded as sentinel-prefixed strings:**
- Issue: Provider output uses literal `<STOP>` and `<TOOL_CALL>` prefixes followed by ad hoc JSON. There is no typed provider protocol, response envelope, schema version, or parser abstraction.
- Files: `02_src/adii/investigator/loop.py`, `02_src/adii/investigator/provider.py`, `02_src/tests/unit/test_investigator_loop.py`
- Impact: Provider integration is tightly coupled to exact string formatting, malformed responses raise low-level exceptions, and later structured-decision support risks accumulating more prefix parsing in the loop.
- Fix approach: Define an internal parsed-response type outside the frozen shared contracts, validate provider output at one boundary, and have the loop consume typed stop/tool/decision variants.

**Trace and usage invariants are documented but not enforced:**
- Issue: `InvestigationRun` accepts caller-supplied `tool_calls`, `model_turns`, and trace sequences without deriving or checking them. It also does not verify that the run and context incident identifiers agree or that trace sequences are contiguous and unique.
- Files: `02_src/adii/contracts/core.py`, `02_src/adii/examples/walkthrough.py`, `02_src/adii/reporting/render.py`, `02_src/tests/contract/test_contracts.py`
- Impact: A run can claim counters that disagree with its trace, undermining the harness-owned telemetry requirement and producing internally inconsistent archives or reports.
- Fix approach: Construct completed runs through a harness-owned builder that derives counters and validates incident identity and trace ordering. Keep contract changes behind the required cross-boundary review.

**Generated status measures lines, not capability completion:**
- Issue: A package is classified as implemented as soon as it contains nontrivial Python lines, while milestone checkboxes remain manually controlled in the build plan.
- Files: `02_src/scripts/sync_status.py`, `02_src/docs/current_status.md`, `02_src/docs/build_plan.md`, `02_src/tests/architecture/test_status_is_current.py`
- Impact: `current_status.md` can correctly report that code exists while still giving little signal about which behaviors are integrated or production-capable. Readers must interpret package presence and milestone completion separately.
- Fix approach: Preserve the generated page but add machine-derived capability signals only when a stable executable check exists; never infer milestone completion from file presence.

**Demo fixtures duplicate a schema that is intentionally separate from production contracts:**
- Issue: Five hand-authored run documents use `contracts/demo/v0`, including evaluation-shaped data and presentation-only fields that do not map directly to the eight core contracts.
- Files: `02_src/adii/demo/CONTRACT.md`, `01_data/demo/fixtures/duplicate-accepted/run.json`, `01_data/demo/fixtures/repair-rejected/run.json`, `02_src/adii/contracts/core.py`
- Impact: Feature work can accidentally copy demo-only fields or assumptions into runtime code, and hand-maintained projections can drift from the real run format while still rendering successfully.
- Fix approach: Treat `02_src/adii/demo/CONTRACT.md` as an orientation-only schema. Generate fixtures from the executable demo world once `01_data/demo/world/` exists, with an explicit projection step from production artifacts.

## Known Bugs

**Non-finite costs pass `InvestigationRun` validation:**
- Symptoms: `api_cost_usd=float("nan")` and `api_cost_usd=float("inf")` both construct successfully because the only check is `< 0`. The renderer then emits `nan` or `inf` as if it were a legitimate cost.
- Files: `02_src/adii/contracts/core.py`, `02_src/adii/reporting/render.py`, `02_src/tests/contract/test_contracts.py`, `02_src/docs/inherited/CONFORMANCE.md`
- Trigger: Construct an `InvestigationRun` with a non-finite `api_cost_usd`.
- Workaround: Validate numeric inputs with `math.isfinite` before constructing a run; add contract tests for NaN, positive infinity, negative infinity, and booleans.

**Frozen contract values are shallowly mutable:**
- Symptoms: Callers can mutate `ToolCall.arguments`, `ToolResult.content`, `TraceEvent.payload`, and `InvestigationDecision.patch` after construction even though their dataclasses are frozen.
- Files: `02_src/adii/contracts/core.py`, `02_src/tests/contract/test_contracts.py`
- Trigger: Assign through a nested dictionary, such as `event.payload["status"] = "OK"`.
- Workaround: Copy and freeze nested mappings at authority boundaries, or serialize immutable snapshots before hashing, validation, and archival. Add tests that mutation cannot change accepted evidence or decisions.

**Malformed tool-call messages crash the investigator loop:**
- Symptoms: Invalid JSON raises `json.JSONDecodeError`; missing `name` or `arguments` raises `KeyError`; wrong top-level shapes can raise `TypeError` or `AttributeError`. These failures have no trace classification and are not returned to the provider as a retryable model error.
- Files: `02_src/adii/investigator/loop.py`, `02_src/tests/unit/test_investigator_loop.py`, `02_src/docs/inherited/CONFORMANCE.md`
- Trigger: Return `<TOOL_CALL>{not-json` or a JSON object without the required fields from a provider.
- Workaround: Parse and schema-check inside the loop boundary, emit a classified trace event/result, and allow correction within the remaining budget. Do not let executor-specific validation stand in for the loop-owned guard.

**Executor and provider exceptions escape without a terminal trace:**
- Symptoms: `provider.respond()` and `executor.execute()` are called without an exception-classification boundary. A provider failure or tool implementation exception ends the run before an archiveable terminal event is produced.
- Files: `02_src/adii/investigator/loop.py`, `02_src/adii/investigator/provider.py`, `02_src/tests/unit/fakes.py`, `02_src/docs/inherited/CONFORMANCE.md`
- Trigger: Use an exhausted scripted provider or an executor that raises instead of returning `ToolResult(status="ERROR")`.
- Workaround: Classify provider, model-output, tool, and platform failures separately; append the terminal event before propagating or returning a failed-run result.

**A missing or corrupt demo fixture produces a server-side exception:**
- Symptoms: `index()` assumes every ordered slug loads successfully and immediately subscripts the result; invalid JSON and missing required keys also propagate from request handling.
- Files: `02_src/adii/demo/server.py`, `01_data/demo/fixtures/`, `02_src/tests/integration/test_front_door_invariants.py`
- Trigger: Remove, truncate, or structurally corrupt any `run.json` listed in `ORDER`, then request `/api/runs`.
- Workaround: Validate fixtures at startup and fail with one explicit diagnostic, or return a structured 500 response without partially serving the run list.

## Security Considerations

**Architecture fitness tests are bypassable by ordinary Python access patterns:**
- Risk: The filesystem guard detects only a bare `open()` call. `pathlib.Path.read_text()`, `os.open`, aliases, dynamic imports, and reflective access can bypass it. Outside-world checks ignore relative imports and match only a short module denylist. The judge boundary is enforced primarily through string matching.
- Files: `02_src/tests/architecture/test_boundaries.py`, `02_src/docs/architecture.md`, `02_src/docs/agent_briefing.md`
- Current mitigation: CI runs the architecture suite separately on all three operating systems, and the investigator currently has no direct outside-world imports.
- Recommendations: Enforce allowed dependency edges rather than a small forbidden-name list; analyze resolved relative imports and dangerous calls/attributes; add adversarial tests proving `pathlib`, `os`, import aliases, and dynamic imports are rejected.

**Patch authorization is represented but not enforceable in current contracts:**
- Risk: `IncidentContext.permitted_write_paths` and `InvestigationDecision.patch` are unrelated string containers. A decision can name arbitrary absolute or traversal paths, and shallow mutation can change a patch after validation.
- Files: `02_src/adii/contracts/core.py`, `02_src/adii/investigator/loop.py`, `02_src/adii/tools/README.md`
- Current mitigation: No production repair application exists, and the architecture requires all environment access to pass through `02_src/adii/tools/`.
- Recommendations: Resolve and canonicalize repair targets inside the tool/validation boundary, reject absolute and escaping paths, bind validation to an immutable candidate snapshot, and test symlink and path-traversal cases.

**Repository-wide JSON scanning can read unrelated sensitive workspace files:**
- Risk: A front-door test recursively reads every `*.json` below the repository, excluding only `.git`, `node_modules`, and `.venv`. A locally present credential JSON or large generated tree is still opened even when unrelated to ADII data.
- Files: `02_src/tests/integration/test_front_door_invariants.py`, `.gitignore`, `01_data/README.md`
- Current mitigation: The test does not print full file contents and tracked data is intentionally team-visible.
- Recommendations: Restrict the scan to tracked files or explicitly governed data/config directories, and exclude credential patterns and ignored paths without weakening the evaluation-material check.

**Dependency and CI bootstrap integrity is not fully pinned:**
- Risk: Test tools are version-pinned, but the PEP 517 build dependency `hatchling` is unconstrained, CI upgrades `pip` to the latest release, and GitHub Actions use mutable major-version tags instead of commit SHAs.
- Files: `pyproject.toml`, `requirements.txt`, `.github/workflows/ci.yml`
- Current mitigation: Runtime dependencies are empty; Python is restricted to 3.12; pytest and Ruff are exact-pinned in `requirements.txt`.
- Recommendations: Pin the build backend range/version, use a constraints or lock strategy with hashes for reproducible qualification, avoid an unconditional latest-pip upgrade, and pin third-party actions by commit SHA.

**Review enforcement is configured with placeholder identities:**
- Risk: CODEOWNERS entries reference `@TEAMMATE-1` through `@TEAMMATE-4`, so shared-surface and cross-review rules cannot take effect until valid GitHub identities replace them.
- Files: `.github/CODEOWNERS`, `.github/pull_request_template.md`, `02_src/docs/review_playbook.md`
- Current mitigation: The PR template states the review and author-understanding gates.
- Recommendations: Replace placeholders with valid team handles and configure branch protection to require CODEOWNERS review and passing CI.

## Performance Bottlenecks

**Accumulated observation state grows and copies without a bound:**
- Problem: Every tool result is retained forever; each append rebuilds the entire tuple, and the full tuple is supplied to every provider call.
- Files: `02_src/adii/investigator/state.py`, `02_src/adii/investigator/loop.py`, `02_src/adii/investigator/provider.py`
- Cause: `state = InvestigationState(observations=(*state.observations, result))` is O(n) per append, producing O(n²) copying across long runs, while result payload size is unconstrained.
- Improvement path: Enforce tool-call and result-size budgets, store observations in a builder-owned append-efficient structure, and construct bounded provider context deliberately rather than replaying every raw result.

**Tool and model payloads are copied into trace events without size limits:**
- Problem: Raw arguments, results, and model responses are retained in memory for the duration of the loop.
- Files: `02_src/adii/investigator/loop.py`, `02_src/adii/contracts/core.py`, `02_src/adii/tools/README.md`
- Cause: The tool layer that must cap rows and line windows is still a scaffold, and the loop imposes no byte/token ceiling.
- Improvement path: Bound results at execution, cap serialized event size, preserve explicit truncation metadata, and keep full artifacts only in the authority-owned archive where policy permits.

**Repository-wide recursive tests scale with unrelated files:**
- Problem: Documentation-link and evaluation-marker checks traverse the entire repository, read every Markdown or JSON file, and do not consistently honor ignored/generated directories.
- Files: `02_src/tests/architecture/test_documentation_links.py`, `02_src/tests/integration/test_front_door_invariants.py`
- Cause: Both checks use `Path.rglob()` from the repository root with hand-maintained exclusions.
- Improvement path: Enumerate tracked files or constrained roots and share one exclusion policy so build artifacts and local workspaces do not increase test cost or create false positives.

## Fragile Areas

**The authority-boundary enforcement suite:**
- Files: `02_src/tests/architecture/test_boundaries.py`, `02_src/docs/architecture.md`, `02_src/docs/inherited/CONFORMANCE.md`
- Why fragile: High-value rules depend on AST/string heuristics with incomplete coverage. A harmless import refactor can evade a rule without any test failure, while adding modules requires manually extending deny lists.
- Safe modification: Add failing bypass examples first, then strengthen dependency analysis. Treat any relaxation as a cross-boundary architectural decision.
- Test coverage: Direct imports and bare `open()` are covered; `pathlib`, `os`, aliases, relative imports, dynamic imports, and indirect dependency chains are not.

**The shared contract module:**
- Files: `02_src/adii/contracts/core.py`, `02_src/adii/contracts/__init__.py`, `02_src/tests/contract/test_contracts.py`
- Why fragile: Eight types are consumed across every boundary, yet nested mutable values and weak runtime type/finite-number checks permit objects to become invalid after construction.
- Safe modification: Do not edit the public contract casually. Add contract tests and obtain cross-boundary review; prefer boundary-owned builders/adapters when an invariant does not belong in the shared vocabulary.
- Test coverage: Basic emptiness, disposition/patch, validation presence, status, and negative counters are covered; deep immutability, finite numbers, counter/trace agreement, sequence integrity, and identifier consistency are not.

**The minimal investigator loop:**
- Files: `02_src/adii/investigator/loop.py`, `02_src/adii/investigator/provider.py`, `02_src/tests/unit/test_investigator_loop.py`
- Why fragile: Parsing, orchestration, tool dispatch, state accumulation, tracing, and budgeting are combined in one function with untyped collaborators and no comprehensive failure boundary.
- Safe modification: Extract provider-response parsing and typed collaborator protocols without allowing the investigator to import validation/evaluation or access the environment directly. Preserve deterministic fake-provider tests.
- Test coverage: Explicit stop, turn budget, basic tool round trips, and executor-returned statuses are covered; malformed response recovery, raised collaborator exceptions, time/cost/tool-call budgets, terminal decisions, and archival are not.

**The report renderer trusts arbitrary trace payload shapes:**
- Files: `02_src/adii/reporting/render.py`, `02_src/adii/contracts/core.py`, `02_src/tests/integration/test_walkthrough.py`
- Why fragile: Payload dictionaries are not schema-validated. Missing keys, non-list `rows`, malformed validation data, or mutated mappings can raise during rendering.
- Safe modification: Validate an artifact before rendering and render unknown/malformed events as explicit diagnostic sections instead of throwing away the whole report.
- Test coverage: One accepted-repair golden report is covered; rejected repair, no-repair, escalation, malformed event, non-finite cost, and partial-failure rendering are absent from the production renderer tests.

**The demo server and clients assume a fixed, trusted fixture set:**
- Files: `02_src/adii/demo/server.py`, `02_src/adii/demo/web/app.js`, `02_src/adii/demo/web/learn.js`, `01_data/demo/fixtures/`
- Why fragile: Startup performs no schema validation; clients assume nonempty lists and complete nested keys; much rendering uses `innerHTML` with a local escape helper that does not escape quotes.
- Safe modification: Keep the service bound to loopback, validate all fixtures before serving, use `textContent`/DOM construction for data values, and add explicit empty/error UI states.
- Test coverage: Fixture content invariants are tested, but HTTP error behavior, corrupt fixtures, client rendering, escaping, and empty fixture lists are not.

## Scaling Limits

**Investigation budgets cover turns only:**
- Current capacity: `max_turns` is the single enforced bound in the loop.
- Limit: Tool calls, wall-clock time, cost, context size, result size, and trace size are unlimited; one slow provider request is not interruptible by the current API.
- Scaling path: Add independently classified tool-call, wall-clock, cost, and context limits, with post-request enforcement and trace events naming the bound hit.
- Files: `02_src/adii/investigator/loop.py`, `02_src/docs/inherited/CONFORMANCE.md`, `02_src/docs/build_plan.md`

**The demo is intentionally a five-run local orientation service:**
- Current capacity: Five fixture runs are loaded from `01_data/demo/fixtures/` and served by a loopback `ThreadingHTTPServer`.
- Limit: No authentication, pagination, concurrency control, persistent state, schema migration, or production hardening exists; the browser orientation page fetches all runs eagerly.
- Scaling path: Do not scale this server into the product. Keep it as an executable explanation and build production runtime/reporting entry points separately.
- Files: `02_src/adii/demo/server.py`, `02_src/adii/demo/web/learn.js`, `02_src/adii/demo/README.md`

**No run archive exists:**
- Current capacity: One walkthrough run is reconstructed in memory from committed fixture files and rendered to stdout.
- Limit: There is no atomic persistence, retry naming, strict JSON validation, schema version dispatch, or partial-failure record, so repeatable batch execution and auditability are unavailable.
- Scaling path: Implement an append-only, schema-versioned artifact writer with strict RFC-8259 serialization, atomic finalization, retry-safe naming, and per-unit failure isolation.
- Files: `02_src/adii/examples/walkthrough.py`, `02_src/adii/reporting/render.py`, `02_src/docs/inherited/CONFORMANCE.md`

## Dependencies at Risk

**Hatchling build backend:**
- Risk: `hatchling` has no version bound even though clean-clone installation depends on it in an isolated build environment.
- Impact: A new backend release can alter or break installation without a repository change, weakening the stated reproducibility guarantee.
- Migration plan: Pin a qualified backend version/range and include it in the dependency qualification/upgrade process.
- Files: `pyproject.toml`, `requirements.txt`, `.github/workflows/ci.yml`

**GitHub Actions bootstrap dependencies:**
- Risk: `actions/checkout@v4` and `actions/setup-python@v5` are tag-pinned rather than immutable-SHA-pinned, and CI downloads the latest pip.
- Impact: CI behavior and supply-chain inputs can change independently of source control.
- Migration plan: Pin action SHAs with version comments and qualify pip/build tooling through an explicit constraints update.
- Files: `.github/workflows/ci.yml`

**No production model or data-client dependency is selected:**
- Risk: The runtime dependency list is empty because the provider and tool layers are fake/scaffold implementations. The first SDK/database addition can introduce networking, retry, schema, and platform behavior across the most sensitive boundaries.
- Impact: Provider/tool selection can silently reshape error classification, reproducibility, and cross-platform behavior late in the schedule.
- Migration plan: Keep adapters narrow, inject them behind typed protocols, pin exact qualified versions, and retain a no-network fake path for all core integration tests.
- Files: `pyproject.toml`, `requirements.txt`, `02_src/adii/investigator/provider.py`, `02_src/adii/tools/README.md`

## Missing Critical Features

**Controlled tool registry and executor:**
- Problem: There is no production schema registry, permission check, read-only SQL authorizer, evidence-id generator, or bounded tool result implementation.
- Blocks: Real evidence gathering and meaningful testing of the investigator/tool authority boundary.
- Files: `02_src/adii/tools/__init__.py`, `02_src/adii/tools/README.md`, `02_src/adii/investigator/loop.py`

**Structured terminal investigation decision:**
- Problem: The current loop returns only trace events after `<STOP>` and never constructs an `InvestigationDecision`.
- Blocks: REPAIR/NO_REPAIR/ESCALATE output, evidence citation, candidate repair handoff, validation, and evaluation.
- Files: `02_src/adii/investigator/loop.py`, `02_src/adii/contracts/core.py`, `02_src/docs/build_plan.md`

**Independent validation authority:**
- Problem: Validation has contracts and documentation but no implementation that rebuilds from frozen inputs or applies a candidate patch.
- Blocks: Safe repair acceptance/rejection and the central separation between investigator hypothesis and authoritative verdict.
- Files: `02_src/adii/validation/__init__.py`, `02_src/adii/validation/README.md`, `02_src/adii/contracts/core.py`

**Evaluation authority and freeze lifecycle:**
- Problem: There are no owned answer keys, frozen hashes, explicit version dispatch, scoring implementation, baseline arms, or grounding-key artifact.
- Blocks: Any evidence-backed claim about investigator correctness or the value of tool-mediated investigation.
- Files: `02_src/adii/evaluation/__init__.py`, `02_src/adii/evaluation/README.md`, `02_src/docs/inherited/AUTHORITY_LIFECYCLE.md`, `02_src/docs/inherited/CONTROLS.md`

**Executable operational world:**
- Problem: The canonical three-configuration commerce world is specified but its directory contains only a README; current demo runs are hand-authored fixtures.
- Blocks: Realistic tool integration, independent validation, scenario generation, and an end-to-end vertical slice grounded in executable data.
- Files: `01_data/demo/world/README.md`, `02_src/docs/DATA_WORLD_v0.md`, `01_data/demo/fixtures/`

**Self-contained run artifacts and production reporting:**
- Problem: No schema-versioned archive writer persists messages, tool inputs/results, rationale, patch, validation, model fingerprint, costs, and failure state atomically.
- Blocks: Replay, trustworthy metrics, partial-failure diagnosis, batch evaluation, and milestone M7 onward.
- Files: `02_src/adii/reporting/render.py`, `02_src/adii/reporting/README.md`, `02_src/docs/inherited/CONFORMANCE.md`

## Test Coverage Gaps

**Contract numeric and immutability invariants:**
- What's not tested: NaN/infinity/boolean counters and costs, deep immutability of mapping fields, trace/counter agreement, trace ordering, duplicate IDs, and incident-ID consistency.
- Files: `02_src/adii/contracts/core.py`, `02_src/tests/contract/test_contracts.py`
- Risk: Invalid or mutable authority-crossing values can be scored, hashed, or rendered as legitimate runs.
- Priority: High

**Model-output and collaborator failure classification:**
- What's not tested: Recovery/classification for malformed JSON, missing fields, unsupported schema shapes, provider exceptions, executor exceptions, timeouts, and post-request budget overruns. One test explicitly expects malformed JSON to propagate.
- Files: `02_src/adii/investigator/loop.py`, `02_src/tests/unit/test_investigator_loop.py`, `02_src/docs/inherited/CONFORMANCE.md`
- Risk: Model mistakes become platform crashes and failed units leave no self-contained archive.
- Priority: High

**Architecture-boundary bypasses:**
- What's not tested: Filesystem access via `pathlib`/`os`, import aliases, dynamic imports, indirect dependency chains, and alternative relative-import forms.
- Files: `02_src/tests/architecture/test_boundaries.py`, `02_src/adii/investigator/`
- Risk: Investigator-facing code can reach hidden evaluation material while CI remains green, invalidating all measurements.
- Priority: High

**Real vertical integration:**
- What's not tested: Incident-to-provider-to-real-tool-to-decision-to-independent-validation-to-archive-to-report. Existing integration tests load teaching fixtures and exercise presentation invariants.
- Files: `02_src/tests/integration/test_walkthrough.py`, `02_src/tests/integration/test_front_door_invariants.py`, `02_src/adii/examples/walkthrough.py`
- Risk: Package-level work can pass independently while boundary handoffs, failure paths, and artifact semantics remain incompatible.
- Priority: High

**Reporting outcome and corruption matrix:**
- What's not tested: Production renderer output for REJECT, NO_REPAIR, ESCALATE, malformed trace payloads, unknown event kinds, missing validation, non-finite usage, and partial failures.
- Files: `02_src/adii/reporting/render.py`, `02_src/tests/integration/test_walkthrough.py`
- Risk: Failures and abstentions can be unreadable or crash reporting even though the accepted-repair golden path passes.
- Priority: Medium

**Demo HTTP and browser behavior:**
- What's not tested: Server route behavior under missing/corrupt fixtures, response headers across errors, empty run lists, browser fetch failures, DOM escaping, keyboard behavior, and client rendering.
- Files: `02_src/adii/demo/server.py`, `02_src/adii/demo/web/app.js`, `02_src/adii/demo/web/learn.js`, `02_src/tests/integration/test_front_door_invariants.py`
- Risk: The onboarding front door can break outside the static fixture-content assertions.
- Priority: Medium

**Coverage measurement:**
- What's not tested: No branch or line coverage threshold is configured or reported.
- Files: `pyproject.toml`, `.github/workflows/ci.yml`, `02_src/tests/`
- Risk: New code and failure branches can land without tests while the suite remains green.
- Priority: Medium

---

*Concerns audit: 2026-09-10*
