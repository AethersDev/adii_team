# Technology Stack

**Analysis Date:** 2026-09-10

## Languages

**Primary:**
- Python 3.12 - Application code, contracts, investigator loop, demo server, reporting, repository automation, and tests under `02_src/`; the supported range is `>=3.12,<3.13` in `pyproject.toml`.

**Secondary:**
- JavaScript (browser-native ECMAScript; version not pinned) - Demo data loading and DOM rendering in `02_src/adii/demo/web/app.js` and `02_src/adii/demo/web/learn.js`.
- HTML5 - Demo entry pages in `02_src/adii/demo/web/index.html` and `02_src/adii/demo/web/inspector.html`.
- CSS - Demo presentation in `02_src/adii/demo/web/style.css` and `02_src/adii/demo/web/intro.css`.
- JSON and JSON Lines - Recorded demo and walkthrough artifacts under `01_data/demo/fixtures/` and `01_data/walkthrough/`.
- YAML - GitHub Actions workflow configuration in `.github/workflows/ci.yml`.
- Markdown - Architecture, operating constraints, package guides, and data specifications in `README.md`, `02_src/docs/`, and package-level `README.md` files.

## Runtime

**Environment:**
- CPython 3.12.x - Exact minor version is enforced by `02_src/scripts/check_env.py`; package metadata rejects Python before 3.12 and Python 3.13 or later in `pyproject.toml`.
- Browser runtime - Any modern browser capable of `fetch`, template literals, async/await, and standard DOM APIs runs `02_src/adii/demo/web/app.js` and `02_src/adii/demo/web/learn.js`; no browser version is pinned.

**Package Manager:**
- pip - Installation uses `python -m pip install -r requirements.txt`; no pip version is pinned.
- Editable local package install: `-e .` in `requirements.txt` installs the `adii` distribution from `pyproject.toml`.
- Lockfile: Missing. Reproducibility comes from exact pins for pytest and Ruff in `requirements.txt`; the build backend itself is not version-pinned.

## Frameworks

**Core:**
- Python standard library - All runtime implementation uses modules such as `dataclasses`, `enum`, `json`, `pathlib`, and `http.server`; `pyproject.toml` declares an empty runtime dependency list.
- No application framework - The local demo uses `http.server.ThreadingHTTPServer` and `SimpleHTTPRequestHandler` directly in `02_src/adii/demo/server.py`.
- No model SDK - `02_src/adii/investigator/provider.py` implements a deterministic `ScriptedProvider`; no Anthropic, OpenAI, or other provider package is installed.

**Testing:**
- pytest 9.1.1 - Test runner pinned in `requirements.txt`; configuration in `pyproject.toml` targets `02_src/tests`, adds `02_src` to the import path, and enables quiet output.
- pytest built-in assertions and fixtures - Contract, unit, integration, and architecture suites live under `02_src/tests/`.

**Build/Dev:**
- Hatchling - PEP 517 build backend declared without an exact version in `pyproject.toml`; it packages `02_src/adii` as distribution `adii` version `0.0.1`.
- Ruff 0.16.6 - Linter/import sorter pinned in `requirements.txt`; `pyproject.toml` sets Python 3.12, a 100-character line length, and rule families `E`, `F`, `I`, `UP`, and `B`.
- GitHub Actions - Cross-platform validation in `.github/workflows/ci.yml` runs on Windows, macOS, and Ubuntu using Python 3.12.

## Key Dependencies

**Critical:**
- No third-party runtime dependency - `[project].dependencies = []` in `pyproject.toml`; preserve this unless a dependency is explicitly reviewed.
- `adii` 0.0.1 - The repository's own package, installed editable through `requirements.txt` and sourced from `02_src/adii` via `pyproject.toml`.
- Python standard library - `02_src/adii/contracts/core.py` uses frozen dataclasses and `StrEnum`; `02_src/adii/demo/server.py` supplies the HTTP server; `02_src/adii/examples/walkthrough.py` reads fixture files.

**Infrastructure:**
- pytest 9.1.1 - Clean-clone test dependency in `requirements.txt`; this is development/CI infrastructure, not runtime code.
- Ruff 0.16.6 - Clean-clone lint dependency in `requirements.txt`; CI runs it against `02_src`.
- `actions/checkout@v4` - Repository checkout in `.github/workflows/ci.yml`.
- `actions/setup-python@v5` - Python 3.12 provisioning in `.github/workflows/ci.yml`.

## Configuration

**Environment:**
- Create a Python 3.12 virtual environment, install `requirements.txt`, then run `python 02_src/scripts/check_env.py`; the canonical setup is in `README.md`.
- No environment variables are currently required. `README.md` mentions `ANTHROPIC_API_KEY` only as a future model-loop configuration and explicitly says it is not needed now.
- No `.env` or `.env.*` file is present. Such files are ignored by `.gitignore`; never commit their values.
- Use `python -m ...` entry points rather than shell scripts, as required by `AGENTS.md` and implemented by `02_src/adii/demo/__main__.py` and `02_src/adii/examples/walkthrough.py`.

**Build:**
- `pyproject.toml` - Package metadata, Hatchling wheel source, pytest discovery/import path, and Ruff settings.
- `requirements.txt` - Editable project install plus exact pytest and Ruff pins for clean clones and CI.
- `.github/workflows/ci.yml` - Installation, environment validation, lint, architecture checks, generated-document synchronization, full tests, and walkthrough execution.
- `02_src/scripts/check_env.py` - Enforces CPython 3.12 and verifies that `adii`, pytest, and Ruff are importable.

## Platform Requirements

**Development:**
- CPython 3.12.x and pip, with dependencies installed from `requirements.txt` as documented in `README.md`.
- Windows and macOS are the named developer platforms in `README.md`; commands are Python-module based and avoid Docker, Make, and shell-script requirements.
- Run `python -m ruff check 02_src` and `python -m pytest` before considering a change complete, per `AGENTS.md`.
- The demo binds only to `127.0.0.1:8000` by default in `02_src/adii/demo/server.py` and requires no external network access.

**Production:**
- No production deployment target is configured or detected.
- `.github/workflows/ci.yml` validates Windows, macOS, and Ubuntu but does not publish packages or deploy an application.
- The current executable surface is a local orientation demo (`python -m adii.demo`) and a fixture-backed walkthrough (`python -m adii.examples.walkthrough`), not a production service.

---

*Stack analysis: 2026-09-10*
