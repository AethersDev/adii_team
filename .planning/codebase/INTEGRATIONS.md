# External Integrations

**Analysis Date:** 2026-09-10

## APIs & External Services

**Model Providers:**
- Not detected - Runtime dependencies are empty in `pyproject.toml`, and the current investigator uses the in-process deterministic `ScriptedProvider` in `02_src/adii/investigator/provider.py`.
  - SDK/Client: Not applicable
  - Auth: None
- Anthropic is roadmap-only, not implemented - `README.md` names `ANTHROPIC_API_KEY` as a future setup step, while `02_src/adii/investigator/README.md` states that the first loop uses a fake provider with no API key or network.
  - SDK/Client: Not installed
  - Auth: `ANTHROPIC_API_KEY` is documented as future configuration only and is not currently read by code.

**Local Demo HTTP API:**
- ADII demo server - A loopback-only, read-only teaching API implemented with the Python standard library in `02_src/adii/demo/server.py`.
  - SDK/Client: Browser-native `fetch` in `02_src/adii/demo/web/app.js` and `02_src/adii/demo/web/learn.js`
  - Auth: None; the server binds to `127.0.0.1` and serves local fixture data.
  - Routes: `GET /api/runs`, `GET /api/runs/{slug}`, and `GET /api/runs/{slug}/{trace|validation|evaluation|provenance}` in `02_src/adii/demo/server.py`.

**Third-Party APIs:**
- Not detected - No runtime package, source import, URL, or client call connects application code under `02_src/adii/` to an external API.
- The architectural boundary allows future outside-world access only from `02_src/adii/tools/`, as enforced by `02_src/tests/architecture/test_boundaries.py`; that package is currently scaffold-only according to `02_src/docs/current_status.md`.

## Data Storage

**Databases:**
- Not detected in implemented runtime code.
  - Connection: Not applicable; no database URL or environment variable is read.
  - Client: None; `sqlite3`, an ORM, and database drivers are absent from implemented `02_src/adii/` code.
- A small local, read-only database is planned for `get_schema` and `run_sql` in `02_src/adii/tools/README.md`, but `02_src/adii/tools/__init__.py` contains no implementation and `01_data/demo/world/README.md` marks the operational world as not built.

**File Storage:**
- Local repository fixtures only - `02_src/adii/demo/server.py` reads recorded run JSON from `01_data/demo/fixtures/*/run.json`.
- Local walkthrough fixtures - `02_src/adii/examples/walkthrough.py` reads `incident.json`, `trace.jsonl`, `decision.json`, and `validation.json` from `01_data/walkthrough/`.
- No runtime artifact store is implemented. Reporting currently renders in memory through `02_src/adii/reporting/render.py`; persistence is described as a future build in `02_src/adii/reporting/README.md`.

**Caching:**
- None - `02_src/adii/demo/server.py` returns `Cache-Control: no-store`, and no cache client or cache service is configured.

## Authentication & Identity

**Auth Provider:**
- None
  - Implementation: The local demo API in `02_src/adii/demo/server.py` has no login, account, session, token, OAuth, or authorization middleware and is restricted to loopback binding.
- Tool permissions are domain authorization rather than user identity: `IncidentContext.permitted_write_paths` in `02_src/adii/contracts/core.py` models bounded repair permissions, but no external identity provider supplies them.

## Monitoring & Observability

**Error Tracking:**
- None - No Sentry, OpenTelemetry exporter, hosted monitoring SDK, or equivalent dependency appears in `pyproject.toml`, `requirements.txt`, or imports under `02_src/`.

**Logs:**
- The demo server writes request messages and lifecycle text to standard output through `Handler.log_message()` and `print()` in `02_src/adii/demo/server.py`.
- Investigation events are represented as in-memory `TraceEvent` values in `02_src/adii/contracts/core.py` and emitted by `02_src/adii/investigator/loop.py`; no external trace sink is implemented.
- The walkthrough replays committed `01_data/walkthrough/trace.jsonl`; it does not send telemetry to an external service.

## CI/CD & Deployment

**Hosting:**
- No application hosting or production deployment is configured.
- GitHub hosts source collaboration metadata under `.github/`; the application itself runs locally through `python -m adii.demo` as documented in `README.md`.

**CI Pipeline:**
- GitHub Actions - `.github/workflows/ci.yml` runs on pushes to `main` and pull requests across `windows-latest`, `macos-latest`, and `ubuntu-latest`.
- The workflow uses `actions/checkout@v4` and `actions/setup-python@v5`, installs `requirements.txt`, then runs environment, lint, architecture, generated-document, test, and walkthrough checks.
- No release, package publication, container registry, deployment, or webhook-based delivery job is defined in `.github/workflows/ci.yml`.

## Environment Configuration

**Required env vars:**
- None for the current implementation; `02_src/scripts/check_env.py` checks interpreter/package availability only and does not read environment variables.
- `ANTHROPIC_API_KEY` appears in `README.md` solely as future provider configuration and must not be treated as a current requirement.

**Secrets location:**
- No secret file is present or consumed by code.
- `.gitignore` excludes `.env` and `.env.*`; secrets must remain outside the repository when an external provider is eventually integrated.
- GitHub Actions in `.github/workflows/ci.yml` references no repository or environment secrets.

## Webhooks & Callbacks

**Incoming:**
- None - No webhook receiver or callback endpoint is implemented.
- The local `GET` routes in `02_src/adii/demo/server.py` are browser-facing demo endpoints, not external callbacks, and expose only committed fixture data.

**Outgoing:**
- None - Application code sends no webhook or callback requests.
- Browser `fetch` calls in `02_src/adii/demo/web/app.js` and `02_src/adii/demo/web/learn.js` are same-origin calls to the local demo API, not third-party traffic.

---

*Integration audit: 2026-09-10*
