"""The inspector's backend: serves the run archive to the browser, and, when the operator
says so, starts a run against a local model.

    python -m adii.demo                                  # read-only: the archive, nothing else
    python -m adii.demo 8000 --endpoint http://127.0.0.1:8090/v1 \\
        --model Qwen3-4B-Instruct-2507-4bit --served-as default_model    # and live runs

Read-only by default: it lists `01_data/runs/<label>/record.json`, serves each record
verbatim, and serves the static page. A page that can start a run can spend money and
create a first exposure, so launching exists only when the person at the terminal
configured a model — and then only a local endpoint, which costs nothing, with the receipt
written before the investigator runs. No paid provider is reachable from here, ever.

Standard library only: the team repository has zero dependencies and this must not be the
thing that adds one. A launched run executes inside the request that started it, in the
server's own process, and the page watches it through the live trace on other connections;
the response is sent first, so the browser is never held.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..examples.specimens import SPECIMENS
from ..examples.walkthrough import load as load_walkthrough
from ..reporting.record import ARCHIVE, LABEL, REPO, read_record
from ..runtime.__main__ import main as run_main

WEB = Path(__file__).resolve().parent / "web"

# Set from the command line. Empty means read-only: the page can start nothing.
LAUNCH: dict[str, object] = {}
# A run whose live trace has not moved for this long is not running; it died.
STALE_AFTER_S = 180


def incidents() -> list[dict[str, str]]:
    """Every incident a run can be started on: the walkthrough's and the specimens'."""
    context, _ = load_walkthrough()
    return [{"incident_id": c.incident_id, "alert": c.alert}
            for c in (context, *(s.context for s in SPECIMENS))]


def index(root: Path) -> list[dict]:
    """One row per archived run, newest first — only what a run list needs. A record this
    reader cannot load is listed with its error rather than hidden: an archive that quietly
    drops a run is worse than one that shows a broken one."""
    rows = []
    for folder in root.glob("*"):
        if not folder.is_dir():                   # the README beside the runs
            continue
        label, path = folder.name, folder / "record.json"
        if not LABEL.fullmatch(label):        # not a label: the API will not serve it either
            rows.append({"label": label, "error": "the folder's name is not a label"})
            continue
        if not path.is_file():
            rows.append({"label": label, **unfinished(folder)})
            continue
        try:
            record = read_record(path)
        except ValueError as why:      # not JSON, not this schema, a field missing or misshapen
            rows.append({"label": label, "error": str(why)})
            continue
        rows.append({
            "label": label,
            "incident_id": record.context.incident_id,
            "termination": record.termination,
            "disposition": record.decision.disposition.value if record.decision else None,
            "validation": None if record.validation is None
            else ("ACCEPT" if record.validation.accepted else "REJECT"),
            "provider": record.configuration.get("provider"),
            "model": record.configuration.get("model"),
            "api_cost_usd": record.api_cost_usd,
            "written_at": record.provenance.get("written_at"),
        })
    rows.sort(key=lambda row: row.get("written_at") or "~", reverse=True)   # running first
    return rows


def unfinished(folder: Path) -> dict:
    """A reserved label with no record: still running if its live trace moved recently,
    otherwise a run that did not finish — and the row says how far it got."""
    trace, receipt = folder / "trace.jsonl", folder / "receipt.json"
    if trace.is_file() and time.time() - trace.stat().st_mtime < STALE_AFTER_S:
        return {"running": True, "error": None}
    how_far = ("a receipt and a live trace were written, but no record" if trace.is_file()
               else "a receipt was written, but no record" if receipt.is_file()
               else "the label was reserved but no record was written")
    return {"running": False, "error": f"{how_far}; the run did not finish"}


def live_trace(folder: Path) -> dict:
    """A run in progress, as far as it has got: the events streamed so far, and whether
    the record has landed."""
    lines = (folder / "trace.jsonl").read_text(encoding="utf-8").splitlines() \
        if (folder / "trace.jsonl").is_file() else []
    return {"label": folder.name, "events": [json.loads(line) for line in lines if line],
            "finished": (folder / "record.json").is_file(),
            "receipt": (folder / "receipt.json").is_file()}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self) -> None:
        # Nothing here may be cached: a browser showing last week's page over today's
        # archive is a stale inspector that looks current.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def route(self) -> list[str]:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        return path.strip("/").split("/")

    def do_GET(self) -> None:  # noqa: N802  (stdlib naming)
        parts = self.route()
        if parts[0] != "api":
            return super().do_GET()
        if parts == ["api", "runs"]:
            return self.send_json(index(ARCHIVE))
        if parts == ["api", "incidents"]:
            return self.send_json(incidents())
        if parts == ["api", "launch"]:
            return self.send_json({"enabled": bool(LAUNCH), **LAUNCH})
        if parts[:2] == ["api", "runs"] and len(parts) in (3, 4):
            label = parts[2]
            # LABEL first: a label that is not one path segment never reaches the filesystem,
            # where a backslash is a directory separator on Windows.
            if not LABEL.fullmatch(label) or not (ARCHIVE / label).is_dir():
                return self.send_json({"error": f"no run {label!r}"}, 404)
            if len(parts) == 4 and parts[3] == "trace":
                return self.send_json(live_trace(ARCHIVE / label))
            record = ARCHIVE / label / "record.json"
            if len(parts) == 3 and record.is_file():
                return self.send(record.read_bytes())   # verbatim: what was archived is shown
            return self.send_json({"error": f"no run {label!r}"}, 404)
        return self.send_json({"error": "no such endpoint"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        """Start a run. Refused unless the operator configured a local model when starting
        the server. The label is answered at once; the run then executes in this request's
        thread while the page watches the live trace."""
        if self.route() != ["api", "runs"]:
            return self.send_json({"error": "no such endpoint"}, 404)
        if not LAUNCH:
            return self.send_json({"error": "this inspector is read-only: start it with "
                                            "--model to allow runs against a local model"}, 403)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or b"{}"))
        incident = body.get("incident")
        if incident not in {i["incident_id"] for i in incidents()}:
            return self.send_json({"error": f"no such incident {incident!r}"}, 400)
        now = datetime.now(UTC)
        label = f"{incident}-{now:%Y%m%dT%H%M%S}-{now.microsecond // 1000:03d}Z"
        self.send_json({"label": label})              # the page navigates and starts watching
        self.wfile.flush()
        run_main(["--incident", incident, "--provider", "local", "--label", label, "--no-report",
                  "--archive", str(ARCHIVE),
                  "--endpoint", str(LAUNCH["endpoint"]), "--model", str(LAUNCH["model"]),
                  "--max-turns", str(LAUNCH["max_turns"]),
                  *(["--served-as", str(LAUNCH["served_as"])] if LAUNCH.get("served_as") else [])])

    def send_json(self, payload: object, status: int = 200) -> None:
        self.send(json.dumps(payload, indent=2, allow_nan=False).encode("utf-8"), status)

    def send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.address_string()} {fmt % args}")


def main(port: int = 8000, launch: dict[str, object] | None = None) -> int:
    LAUNCH.clear()
    LAUNCH.update(launch or {})
    runs = index(ARCHIVE)
    print(f"ADII run inspector — http://127.0.0.1:{port}")
    print(f"  {len(runs)} archived run(s) in {ARCHIVE.relative_to(REPO)}.", end=" ")
    if LAUNCH:
        print(f"Runs may be started from the page, against {LAUNCH['model']} at "
              f"{LAUNCH['endpoint']} — a local endpoint, nothing is spent.")
    else:
        print("Read-only: start with --model to allow runs against a local model.")
    if not runs:
        print("  Produce one now:  python -m adii.runtime --incident demo-learning-001 "
              "--provider scripted")
    print()
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as taken:                 # the port is held, or not ours to bind
        print(f"could not listen on 127.0.0.1:{port}: {taken.strerror}.")
        print(f"  Another inspector may be running. Pick a port:  python -m adii.demo {port + 1}")
        return 1
    with httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0
