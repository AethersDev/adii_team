# Coding Conventions

**Analysis Date:** 2026-09-10

## Naming Patterns

**Files:**
- Use lowercase `snake_case.py` for Python modules, as in `02_src/adii/investigator/provider.py`, `02_src/adii/reporting/render.py`, and `02_src/scripts/sync_status.py`.
- Name tests `test_<subject>.py` and place them under the layer they protect: `02_src/tests/unit/test_investigator_loop.py`, `02_src/tests/contract/test_contracts.py`, `02_src/tests/architecture/test_boundaries.py`, or `02_src/tests/integration/test_walkthrough.py`.
- Keep package interfaces in `__init__.py`; re-export only the intended public vocabulary, following `02_src/adii/contracts/__init__.py` and `02_src/adii/reporting/__init__.py`.
- Use lowercase kebab-case for demo fixture directories such as `01_data/demo/fixtures/repair-accepted/` and lowercase names for static assets such as `02_src/adii/demo/web/learn.js`.

**Functions:**
- Use `snake_case` for Python functions and methods: `render_run`, `implementation_lines`, `received_observations`, and `test_budget_allows_normal_completion` in `02_src/adii/reporting/render.py`, `02_src/scripts/sync_status.py`, `02_src/adii/investigator/provider.py`, and `02_src/tests/unit/test_investigator_loop.py`.
- Prefix internal helpers with `_`, as in `_wrap`, `_arguments`, and `_summary` in `02_src/adii/reporting/render.py` and `_check` in `02_src/scripts/check_env.py`.
- Name tests as complete behavioral claims, not implementation labels; examples include `test_zero_budget_refuses_provider_call_and_attaches_terminal_trace` in `02_src/tests/unit/test_investigator_loop.py` and `test_the_investigator_cannot_reach_the_judge` in `02_src/tests/architecture/test_boundaries.py`.
- Preserve externally imposed names with a narrow lint suppression. `Handler.do_GET` in `02_src/adii/demo/server.py` uses `# noqa: N802` because the standard-library base class defines that spelling.
- Use camelCase for browser-side JavaScript functions (`outcomeChapter`, `authorityChain`, `runRecord`) in `02_src/adii/demo/web/learn.js` and `02_src/adii/demo/web/app.js`.

**Variables:**
- Use `snake_case` for Python locals and parameters: `turns_taken`, `turn_index`, `root_cause_summary`, and `permitted_write_paths` in `02_src/adii/investigator/loop.py` and `02_src/adii/contracts/core.py`.
- Use leading underscores for private instance state (`_responses`, `_cursor`, `_received_context`) in `02_src/adii/investigator/provider.py`.
- Use `UPPER_SNAKE_CASE` for module constants (`STOP_SIGNAL`, `TOOL_CALL_PREFIX`, `REQUIRED`, `FIXTURES`, `OUTSIDE_WORLD`) in `02_src/adii/investigator/loop.py`, `02_src/scripts/check_env.py`, `02_src/adii/demo/server.py`, and `02_src/tests/architecture/test_boundaries.py`.
- Prefer concrete domain names (`incident`, `provider`, `executor`, `trace`, `observation`) over generic containers in `02_src/adii/investigator/loop.py`.

**Types:**
- Use `PascalCase` for classes, enums, dataclasses, and exceptions: `IncidentContext`, `Disposition`, `InvestigationState`, `ScriptedProvider`, and `TurnBudgetExceededError` in `02_src/adii/contracts/core.py` and `02_src/adii/investigator/`.
- Suffix exceptional conditions with `Error`; use a domain-specific name when callers must distinguish it from generic failures, as in `ScriptExhaustedError` in `02_src/adii/investigator/provider.py` and `TurnBudgetExceededError` in `02_src/adii/investigator/loop.py`.
- Model shared values as frozen dataclasses and closed enums in `02_src/adii/contracts/core.py`; do not introduce parallel dictionaries or mutable contract objects in another package.
- Use Python 3.12 built-in generics and union syntax (`list[str]`, `tuple[TraceEvent, ...]`, `ToolResult | None`) throughout `02_src/adii/`.

## Code Style

**Formatting:**
- Ruff is the sole configured style tool. Use the 100-character line length and Python 3.12 target declared in `pyproject.toml`.
- No Black, isort, Prettier, ESLint, or Biome configuration is present. Format Python to satisfy Ruff and retain the established compact wrapping in `02_src/adii/reporting/render.py` and `02_src/tests/contract/test_contracts.py`.
- Indent Python with four spaces. Use blank lines between module docstrings/imports, top-level definitions, and logical test phases, following `02_src/adii/investigator/provider.py` and `02_src/tests/unit/test_investigator_provider.py`.
- Use UTF-8 for all explicit file reads and writes and normalize generated text to `\n`, following `02_src/scripts/sync_status.py`, `02_src/scripts/sync_briefing.py`, and `02_src/adii/examples/walkthrough.py`.
- Keep the browser demo dependency-free and use its existing two-space JavaScript indentation and semicolon-terminated statements in `02_src/adii/demo/web/app.js` and `02_src/adii/demo/web/learn.js`.

**Linting:**
- Run `python -m ruff check 02_src`; this is the local and CI lint contract in `README.md`, `AGENTS.md`, and `.github/workflows/ci.yml`.
- Ruff enables `E`/`F` correctness, `I` import sorting, `UP` Python upgrades, and `B` bugbear rules in `pyproject.toml`.
- Add a precise inline `# noqa: <rule>` only when an external API forces a convention mismatch, as demonstrated by `# noqa: N802` in `02_src/adii/demo/server.py`.
- Do not silently add formatters, linters, runtime packages, or developer dependencies; dependency changes require explicit review under `requirements.txt` and `AGENTS.md`.

## Import Organization

**Order:**
1. Place `from __future__ import annotations` immediately after the module docstring when the module uses it, as in `02_src/adii/contracts/core.py` and `02_src/adii/examples/walkthrough.py`.
2. Group standard-library imports next (`json`, `pathlib`, `dataclasses`, `collections.abc`).
3. Place third-party imports such as `pytest` after standard-library imports in tests, as in `02_src/tests/unit/test_investigator_loop.py`.
4. Place package and relative imports last. Production modules use relative imports within `adii`, while tests import the public `adii` package and reserve relative imports for test-only collaborators.

**Path Aliases:**
- No configured aliases exist. `pyproject.toml` adds `02_src` to pytest's Python path, so tests import `adii.contracts` and `adii.investigator.loop` directly.
- Use relative imports inside production packages (`from ..contracts import ...`, `from .state import ...`) as in `02_src/adii/investigator/loop.py`.
- Import public surfaces from package roots where available (`from adii.contracts import ToolResult`, `from adii.reporting import render_run`) based on `02_src/adii/contracts/__init__.py` and `02_src/adii/reporting/__init__.py`.
- Keep script loading isolated to test infrastructure. `02_src/tests/unit/conftest.py` builds the `scripts_check_env_shim` module because `02_src/scripts/` intentionally is not a package.

## Error Handling

**Patterns:**
- Validate public inputs at their construction or API boundary and raise `ValueError` with an actionable invariant message. Examples are contract `__post_init__` methods in `02_src/adii/contracts/core.py`, the `max_turns` guard in `02_src/adii/investigator/loop.py`, and empty-script validation in `02_src/adii/investigator/provider.py`.
- Reject booleans explicitly when an integer is required because `bool` subclasses `int`; `run` in `02_src/adii/investigator/loop.py` checks this before invoking collaborators.
- Use a named exception when callers need structured failure data. `TurnBudgetExceededError` retains both `limit` and the terminal `trace` in `02_src/adii/investigator/loop.py`; `ScriptExhaustedError` distinguishes an exhausted fake provider in `02_src/adii/investigator/provider.py`.
- Represent tool outcomes as `ToolResult.status`, not exceptions: `DENIED`, `REJECTED`, and `ERROR` remain distinct and are fed back into the loop in `02_src/adii/contracts/core.py` and `02_src/tests/unit/fakes.py`.
- Do not catch an exception merely to relabel it. Unhandled malformed prefixed JSON currently propagates `json.JSONDecodeError` from `02_src/adii/investigator/loop.py`, and `02_src/tests/unit/test_investigator_loop.py` pins that behavior.
- Return integer exit codes from command entry points and raise `SystemExit(main(...))` only in the `if __name__ == "__main__"` adapter, following `02_src/scripts/check_env.py`, `02_src/scripts/sync_status.py`, and `02_src/adii/demo/server.py`.
- Preserve authority failures as traceable facts. A budget stop appends `budget_exceeded` before raising in `02_src/adii/investigator/loop.py`; any future failure path must leave an inspectable trace rather than relying on terminal output.

## Logging

**Framework:** console output only; no logging package is configured.

**Patterns:**
- Use `print` for human-facing CLI status in `02_src/scripts/check_env.py`, `02_src/scripts/sync_status.py`, and `02_src/adii/examples/walkthrough.py`.
- Use structured `TraceEvent` values for runtime observability in `02_src/adii/investigator/loop.py`; do not substitute prose logs for evidence that a run must archive or score.
- Keep demo HTTP request output localized to `Handler.log_message` in `02_src/adii/demo/server.py`.
- Never claim a behavior occurred unless it appears in the trace. Counters and reports consume trace-owned facts as required by `02_src/docs/inherited/CONFORMANCE.md`.

## Comments

**When to Comment:**
- Explain purpose, authority, and non-obvious constraints rather than restating syntax. Strong examples are the module docstrings in `02_src/adii/contracts/core.py`, `02_src/tests/architecture/test_boundaries.py`, and `02_src/adii/demo/server.py`.
- Document why an invariant exists when it prevents a known conformance failure, as in the budget tests in `02_src/tests/unit/test_investigator_loop.py` and boundary tests in `02_src/tests/architecture/test_boundaries.py`.
- Use short inline comments only for surprising mechanics or provenance, such as counter derivation in `02_src/tests/integration/test_walkthrough.py` and the standard-library naming suppression in `02_src/adii/demo/server.py`.
- Avoid ownership comments by person. Capabilities and paths organize the system, as enforced by `AGENTS.md` and `.github/CODEOWNERS`.

**JSDoc/TSDoc:**
- Not applicable; the JavaScript demo uses file-level and section comments rather than JSDoc in `02_src/adii/demo/web/app.js` and `02_src/adii/demo/web/learn.js`.
- Python public classes/functions and significant test helpers use concise docstrings, while self-evident private helpers may omit them. Follow `02_src/adii/investigator/provider.py` and `02_src/tests/architecture/test_boundaries.py`.

## Function Design

**Size:** Keep one responsibility per function. Small validators and render helpers are preferred (`_check` in `02_src/scripts/check_env.py`, `_summary` in `02_src/adii/reporting/render.py`); orchestration functions such as `run` in `02_src/adii/investigator/loop.py` may be longer when they keep the state transition visible end to end.

**Parameters:**
- Type production parameters and returns. Use keyword-only parameters for limits and collaborator options, as in `run(..., *, max_turns)` in `02_src/adii/investigator/loop.py` and `ScriptedProvider.respond(*, observation=..., observations=...)` in `02_src/adii/investigator/provider.py`.
- Prefer immutable tuple inputs/outputs at public observation and trace boundaries in `02_src/adii/investigator/provider.py` and `02_src/adii/investigator/loop.py`.
- Accept `object` at intentionally untrusted rendering boundaries, then narrow with `isinstance`, as `_arguments` and `_summary` do in `02_src/adii/reporting/render.py`.

**Return Values:**
- Return contract values and immutable tuples from runtime code rather than mutable internal storage. `ScriptedProvider` copies received data into tuples and `run` returns `tuple[TraceEvent, ...]` in `02_src/adii/investigator/`.
- Return `None` only for an explicit absence (`demo.server.load` in `02_src/adii/demo/server.py`); do not use it to hide tool refusal or platform errors, which belong in `ToolResult.status`.
- Keep command functions deterministic around an integer exit code (`main() -> int`) in `02_src/scripts/` and `02_src/adii/examples/walkthrough.py`.

## Module Design

**Exports:**
- Keep shared contracts centralized in `02_src/adii/contracts/core.py`; do not edit or invent a contract without explicit cross-boundary approval from `AGENTS.md`.
- Declare intentional package exports through `__all__`, following `02_src/adii/contracts/__init__.py` and `02_src/adii/reporting/__init__.py`.
- Keep private helpers underscored and implementation details in their owning module. Tests should exercise public behavior unless they are architecture fitness tests inspecting source structure.
- Maintain the three enforced boundaries: investigator access only through tools, validation outside the investigator, and evaluation unreachable from the investigator. Tests live in `02_src/tests/architecture/test_boundaries.py`.

**Barrel Files:**
- Python package `__init__.py` files act as narrow barrels only for stable public names. Do not turn scaffold files such as `02_src/adii/tools/__init__.py`, `02_src/adii/validation/__init__.py`, or `02_src/adii/evaluation/__init__.py` into broad import aggregators prematurely.
- JavaScript uses direct classic scripts and has no bundler or barrel-module convention in `02_src/adii/demo/web/`.

---

*Convention analysis: 2026-09-10*
