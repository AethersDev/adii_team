# Testing Patterns

**Analysis Date:** 2026-09-10

## Test Framework

**Runner:**
- pytest 9.1.1 is pinned in `requirements.txt`; `pyproject.toml` permits pytest 8+ for the development dependency group but the clean-clone and CI path uses the exact requirements pin.
- Config: `pyproject.toml`
- Discovery is restricted to `02_src/tests`, `02_src` is added to the Python path, and `-q` is applied to every pytest invocation through `[tool.pytest.ini_options]` in `pyproject.toml`.
- The repository currently defines 74 `test_*` functions before parametrized expansion across `02_src/tests/`.

**Assertion Library:**
- Native Python `assert` plus `pytest.raises` and `pytest.mark.parametrize`; no Hamcrest, Hypothesis, or plugin assertion layer is configured.

**Run Commands:**
```bash
python -m pytest                                      # Run all tests
python -m pytest 02_src/tests/unit                   # Run unit tests
python -m pytest 02_src/tests/contract               # Pin shared contracts
python -m pytest 02_src/tests/architecture -q        # Enforce package and documentation boundaries
python -m pytest 02_src/tests/integration            # Run fixture and walkthrough integration tests
python -m pytest -k investigator                     # Run investigator-focused tests
python -m pytest -x                                  # Stop at first failure during a tight local loop
```

- Watch mode: Not configured. pytest-watch and pytest-xdist are not dependencies in `requirements.txt` or `pyproject.toml`.
- Coverage command: Not configured. No coverage dependency, configuration, threshold, or CI coverage step exists.
- Install first with `python -m pip install -r requirements.txt`; the bare system interpreter may not contain pytest. The environment check is `python 02_src/scripts/check_env.py`.
- Always pair the suite with `python -m ruff check 02_src`, as required by `AGENTS.md` and `.github/workflows/ci.yml`.

## Test File Organization

**Location:**
- Tests are separate from production code under `02_src/tests/`, divided by the kind of contract they protect rather than mirrored one-for-one beside source files.
- Unit behavior lives in `02_src/tests/unit/`, shared data-contract invariants in `02_src/tests/contract/`, dependency and governance fitness rules in `02_src/tests/architecture/`, and cross-component/fixture flows in `02_src/tests/integration/`.
- Test-only collaborators are centralized in `02_src/tests/unit/fakes.py`. Shared pytest bootstrapping is localized to `02_src/tests/unit/conftest.py`.
- Committed golden and scenario data lives outside test code: `01_data/walkthrough/expected_report.txt`, `01_data/walkthrough/*.json`, and declared demo fixtures under `01_data/demo/fixtures/*/run.json`.

**Naming:**
- Files use `test_<subject>.py`; functions use `test_<behavioral_claim>()`.
- Prefer names that state trigger and observable result, such as `test_tool_round_trip_consumes_one_turn_and_budget_blocks_stop` in `02_src/tests/unit/test_investigator_loop.py`.
- Parametrized cases receive readable IDs when paths would otherwise be opaque, using `ids=IDS` in `02_src/tests/integration/test_front_door_invariants.py` and `ids=relative` in `02_src/tests/architecture/test_boundaries.py`.

**Structure:**
```text
02_src/tests/
├── unit/
│   ├── conftest.py
│   ├── fakes.py
│   ├── test_env_check.py
│   ├── test_investigator_loop.py
│   └── test_investigator_provider.py
├── contract/
│   └── test_contracts.py
├── architecture/
│   ├── test_boundaries.py
│   ├── test_briefing_is_current.py
│   ├── test_documentation_links.py
│   └── test_status_is_current.py
└── integration/
    ├── test_front_door_invariants.py
    └── test_walkthrough.py
```

## Test Structure

**Suite Organization:**
```python
def test_zero_budget_refuses_provider_call_and_attaches_terminal_trace():
    provider = ScriptedProvider([STOP_SIGNAL])

    with pytest.raises(TurnBudgetExceededError) as raised:
        run(incident(), provider, FakeToolExecutor(), max_turns=0)

    assert raised.value.limit == 0
    assert raised.value.trace[0].kind == "budget_exceeded"
    assert provider.respond() == STOP_SIGNAL
```

- This arrange/act/assert pattern comes from `02_src/tests/unit/test_investigator_loop.py`: construct deterministic collaborators, invoke one public behavior, then assert both output and collaborator side effects.
- Keep each test focused on one named guarantee, even when several exact assertions are required to prove it.
- Assert domain meaning, ordering, and payload content—not only that code returned. Trace tests in `02_src/tests/unit/test_investigator_loop.py` check event kinds, sequences, turn indexes, payloads, and whether a provider response remained unconsumed.

**Patterns:**
- Setup uses plain helper functions (`incident`, `tool_call_response`, `decision`) in `02_src/tests/unit/test_investigator_loop.py` and `02_src/tests/contract/test_contracts.py`; fixture decorators are not used for simple value construction.
- Teardown is normally unnecessary because unit fakes do no external I/O. Server execution is not started inside the current automated suite.
- Use `pytest.raises(ExpectedError, match="stable message fragment")` to prove failure type and useful diagnostics in `02_src/tests/contract/test_contracts.py` and `02_src/tests/unit/test_investigator_provider.py`.
- Capture the raised object with `as raised` when structured fields or attached trace data are part of the contract, as in `02_src/tests/unit/test_investigator_loop.py`.
- Use explicit boundary pairs and adjacent limits (`n` versus `n - 1`, zero, negative, boolean, float, NaN) for numeric constraints in `02_src/tests/unit/test_investigator_loop.py`.
- Prove determinism by running the same script through fresh collaborators and comparing complete traces in `02_src/tests/unit/test_investigator_loop.py`.
- Use parametrization for a small closed input family or repository-wide path set in `02_src/tests/contract/test_contracts.py` and `02_src/tests/architecture/test_boundaries.py`.
- Use `capsys` for command output and exit-code behavior in `02_src/tests/unit/test_env_check.py` and `02_src/tests/integration/test_walkthrough.py`.

## Mocking

**Framework:** Hand-written fakes; `unittest.mock`, pytest-mock, and monkeypatch are not used.

**Patterns:**
```python
class FakeToolExecutor:
    def __init__(self, *, marker: str | None = None) -> None:
        self.marker = marker
        self.calls: list[ToolCall] = []
        self.results: list[ToolResult] = []

    def execute(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        # Return a real ToolResult with OK, DENIED, REJECTED, or ERROR.
```

- The actual pattern is in `02_src/tests/unit/fakes.py`: fakes record calls and results, return real contract objects, and expose deterministic knobs such as `marker`.
- `ScriptedProvider` in `02_src/adii/investigator/provider.py` is a production-side deterministic model substitute designed for tests; it consumes canned responses and records observations/context.
- `StateAwareFakeProvider` in `02_src/tests/unit/fakes.py` changes its second action based on accumulated observations, enabling a causal multi-step test without a network model.
- `02_src/tests/unit/conftest.py` uses `importlib.util` to make `02_src/scripts/check_env.py` importable without changing `scripts/` into a package; preserve this narrow shim rather than changing production packaging for a test.

**What to Mock:**
- Replace model providers and tool executors at the investigator boundary so unit tests remain deterministic, offline, and free of API keys, following `02_src/tests/unit/test_investigator_loop.py`.
- Record collaborator inputs when delivery semantics matter: `received_observations`, `received_context`, executor `calls`, and executor `results` are asserted directly.
- Use controlled fake statuses to exercise `DENIED`, `REJECTED`, and `ERROR` independently in `02_src/tests/unit/fakes.py`.

**What NOT to Mock:**
- Do not mock shared contract dataclasses. Construct real `IncidentContext`, `ToolCall`, `ToolResult`, `TraceEvent`, and `InvestigationRun` values from `02_src/adii/contracts/`.
- Do not mock the walkthrough renderer or loader in integration tests; `02_src/tests/integration/test_walkthrough.py` loads committed JSON into real contracts and compares the real renderer to a golden report.
- Do not mock filesystem inspection in architecture tests. `02_src/tests/architecture/test_boundaries.py`, `test_documentation_links.py`, and `test_status_is_current.py` intentionally scan the live repository.
- Never substitute investigator rehearsal for independent validation. The authority distinction is pinned in `02_src/tests/contract/test_contracts.py` and `02_src/docs/inherited/CONFORMANCE.md`.

## Fixtures and Factories

**Test Data:**
```python
def incident() -> IncidentContext:
    return IncidentContext(
        incident_id="incident-phase-2",
        alert="A test alert",
        as_of="2026-09-10T00:00:00Z",
    )

def tool_call_response(*, name="fake_tool", arguments=None) -> str:
    intent = {
        "name": name,
        "arguments": {"value": "hello"} if arguments is None else arguments,
    }
    return TOOL_CALL_PREFIX + json.dumps(intent, sort_keys=True)
```

- These helpers come from `02_src/tests/unit/test_investigator_loop.py`. Prefer compact factories with safe defaults and keyword overrides over large repeated object literals.
- Contract tests use a dictionary-override factory (`decision(**overrides)`) in `02_src/tests/contract/test_contracts.py` to vary one invariant at a time.
- Repository scenarios are real files, not generated temporary data: `01_data/walkthrough/` supplies the teaching run and `01_data/demo/fixtures/` supplies front-door cases.
- Every demo fixture containing evaluation-shaped data must declare `"fixture": true` and provenance; `02_src/tests/integration/test_front_door_invariants.py` scans every JSON file to enforce this.

**Location:**
- Unit factories: beside the tests that use them in `02_src/tests/unit/test_investigator_loop.py` and `02_src/tests/contract/test_contracts.py`.
- Reusable unit collaborators: `02_src/tests/unit/fakes.py`.
- Pytest bootstrap: `02_src/tests/unit/conftest.py`.
- Walkthrough golden data: `01_data/walkthrough/`.
- Demo fixture runs: `01_data/demo/fixtures/<slug>/run.json`.

## Coverage

**Requirements:** None enforced. There is no pytest-cov/coverage dependency, `.coveragerc`, threshold, badge, or coverage upload in `requirements.txt`, `pyproject.toml`, or `.github/workflows/ci.yml`.

**View Coverage:**
```bash
# Not available in the repository's declared environment.
# Adding coverage tooling is a reviewed dependency/configuration change, not an implicit command.
```

- Treat the absence of a percentage target as a reason to map tests to behavior and boundaries, not as permission to skip risk-based tests.
- The merge gate is executable behavior: full pytest, Ruff, explicit architecture tests, generated-document drift checks, and an end-to-end walkthrough in `.github/workflows/ci.yml`.

## Test Types

**Unit Tests:**
- `02_src/tests/unit/test_investigator_provider.py` tests deterministic scripted responses, exhaustion, observation delivery, and protection from mutable internal storage.
- `02_src/tests/unit/test_investigator_loop.py` covers explicit stopping, budgets, invalid limit types, trace ordering, tool round-trips, status continuation, deterministic state accumulation, and observation-driven branching.
- `02_src/tests/unit/test_env_check.py` treats either environment exit status as locally informative while asserting the command reports a status; CI separately requires exit code zero through `.github/workflows/ci.yml`.
- Keep unit collaborators free of filesystem, database, network, and subprocess access.

**Contract Tests:**
- `02_src/tests/contract/test_contracts.py` pins shared vocabulary invariants at construction: disposition/patch rules, mandatory validation, closed tool statuses, non-negative counters, and non-empty identifiers.
- Any authorized change to `02_src/adii/contracts/` requires corresponding contract-test updates and cross-boundary review under `AGENTS.md` and `.github/pull_request_template.md`.

**Architecture Tests:**
- `02_src/tests/architecture/test_boundaries.py` parses Python AST/imports and scans source to enforce standard-library-only contracts, tool-only world access, no investigator-to-judge imports, no private repositories, dependency-free demo behavior, and package documentation.
- `02_src/tests/architecture/test_briefing_is_current.py` keeps `AGENTS.md`, `CLAUDE.md`, and `02_src/docs/agent_briefing.md` synchronized.
- `02_src/tests/architecture/test_status_is_current.py` compares generated status text to committed `02_src/docs/current_status.md`.
- `02_src/tests/architecture/test_documentation_links.py` resolves internal Markdown links across the repository.
- A failing architecture test should normally be fixed in implementation or documentation, not weakened; this rule is explicit in `AGENTS.md` and `02_src/tests/architecture/test_boundaries.py`.

**Integration Tests:**
- `02_src/tests/integration/test_walkthrough.py` loads committed files through real contract constructors, checks every authority boundary appears in the narration, compares exact rendered output, and exercises the module entry point.
- `02_src/tests/integration/test_front_door_invariants.py` validates all demo fixture projections, repair mechanisms, escalation evidence, provenance, and the repository-wide placement of evaluation-shaped JSON.
- Integration tests prefer complete domain assertions over HTTP-level mocking; the current demo HTTP server itself has no automated request test.

**E2E Tests:**
- No separate browser automation or E2E framework is used.
- The executable walkthrough is the current smoke-level end-to-end path: CI runs `python -m adii.examples.walkthrough` after pytest in `.github/workflows/ci.yml`.
- `python -m adii.demo` is documented for manual orientation in `README.md` and `02_src/adii/demo/README.md`, but CI does not start or browser-test the server.

## Common Patterns

**Async Testing:**
```python
# Not used. Current Python runtime code and tests are synchronous.
```

- Browser code uses async fetch flows in `02_src/adii/demo/web/learn.js` and `02_src/adii/demo/web/app.js`, but there is no JavaScript test runner or browser harness.
- If async Python is introduced, use pytest support only after adding and documenting the required dependency; no async pytest plugin is currently declared.

**Error Testing:**
```python
with pytest.raises(ValueError, match="non-negative integer"):
    run(
        incident(),
        ScriptedProvider([STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=True,
    )
```

- This pattern from `02_src/tests/unit/test_investigator_loop.py` proves the exact classification and stable diagnostic fragment.
- Also prove the forbidden side effect did not occur. Budget validation tests verify the scripted response remains available, and stop tests verify the executor received no calls.
- For structured domain exceptions, assert attached metadata and trace content, not only the exception class.
- For tool-level bad outcomes, assert normal continuation with a real `ToolResult` status rather than expecting an exception.

**Golden Testing:**
```python
context, run = load()
assert render_run(context, run) == EXPECTED.read_text(encoding="utf-8")
```

- `02_src/tests/integration/test_walkthrough.py` treats `01_data/walkthrough/expected_report.txt` as a committed regression artifact.
- Update the golden file only when the public report intentionally changes and the author can explain the semantic difference.

**Repository Fitness Testing:**
```python
@pytest.mark.parametrize("path", source_files(), ids=relative)
def test_only_the_tool_layer_touches_the_outside_world(path: Path):
    ...
```

- Use live repository enumeration for rules that must apply to every future module, as in `02_src/tests/architecture/test_boundaries.py`.
- Keep allowlists narrow and explain why each exemption exists. Do not relax a path rule to make a new boundary violation pass.

## CI Verification

- `.github/workflows/ci.yml` runs on Windows, macOS, and Ubuntu with Python 3.12 and `fail-fast: false`.
- CI installs only from `requirements.txt`, runs the environment check, Ruff, architecture tests, generated briefing/status drift checks, the full suite, and the walkthrough.
- Before declaring a change complete, run:

```bash
python -m ruff check 02_src
python -m pytest
```

- For changes to generated sources, also run `python 02_src/scripts/sync_briefing.py` or `python 02_src/scripts/sync_status.py` as appropriate and verify no unintended diff remains.

---

*Testing analysis: 2026-09-10*
