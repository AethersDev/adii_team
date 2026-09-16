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
the response is sent first, so the browser is never held. One run at a time: a second is
refused while the archive shows one running.
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
            "evaluation": evaluation_of(folder),
            "incident_id": record.context.incident_id,
            "termination": record.termination,
            "disposition": record.decision.disposition.value if record.decision else None,
            # three states the record distinguishes: accepted; not accepted after checks;
            # not checked at all — `checks_run` empty — which is not a finding about the repair
            "validation": None if record.validation is None
            else ("ACCEPT" if record.validation.accepted
                  else "REJECT" if record.validation.checks_run else "UNCHECKED"),
            "provider": record.configuration.get("provider"),
            "model": record.configuration.get("model"),
            "api_cost_usd": record.api_cost_usd,
            "written_at": record.provenance.get("written_at"),
        })
    rows.sort(key=lambda row: row.get("written_at") or "~", reverse=True)   # running first
    return rows


def evaluation_of(folder: Path) -> str | None:
    """The category the evaluation authority scored this run, when it has; a report this
    reader cannot parse is said to be unreadable rather than dropped."""
    path = folder / "evaluation_report.json"
    if not path.is_file():
        return None
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("category"))
    except ValueError:                        # not JSON: custody's finding, listed as such
        return "unreadable"


def running(folder: Path) -> bool:
    """A reserved label with no record is running while it keeps writing — the folder when
    reserved, then the receipt, then every trace event. Silent for STALE_AFTER_S, it died."""
    if (folder / "record.json").is_file():
        return False
    moved = max(p.stat().st_mtime for p in (folder, folder / "receipt.json", folder / "trace.jsonl")
                if p.exists())
    return time.time() - moved < STALE_AFTER_S


def unfinished(folder: Path) -> dict:
    """A reserved label with no record: running, or a run that did not finish — and then
    the row says how far it got."""
    if running(folder):
        return {"running": True, "error": None}
    trace, receipt = folder / "trace.jsonl", folder / "receipt.json"
    how_far = ("a receipt and a live trace were written, but no record" if trace.is_file()
               else "a receipt was written, but no record" if receipt.is_file()
               else "the label was reserved but no record was written")
    return {"running": False, "error": f"{how_far}; the run did not finish"}


FEEDBACK_LIMITS = {"useful": ("yes", "partly", "no"), "expected": 2000, "by": 80}


def feedback_of(folder: Path) -> list[dict]:
    """Every piece of feedback left on a run, oldest first, as recorded."""
    path = folder / "feedback.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def record_feedback(folder: Path, body: dict) -> dict:
    """Append one operator's feedback beside the record: attributed, bounded, verbatim.
    Raises ValueError with the reason when the body is not feedback this archive keeps."""
    useful, expected, by = body.get("useful"), body.get("expected", ""), body.get("by", "")
    if useful not in FEEDBACK_LIMITS["useful"]:
        raise ValueError("useful must be one of yes, partly, no")
    if not isinstance(expected, str) or not isinstance(by, str):
        raise ValueError("expected and by must be text")
    if len(expected) > FEEDBACK_LIMITS["expected"] or len(by) > FEEDBACK_LIMITS["by"]:
        raise ValueError("expected is limited to 2000 characters and by to 80")
    entry = {"schema": "adii.feedback/v1", "useful": useful, "expected": expected.strip(),
             "by": by.strip() or "an operator",
             "written_at": datetime.now(UTC).isoformat(timespec="seconds")}
    with (folder / "feedback.jsonl").open("a", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(entry, allow_nan=False) + "\n")
    return entry


def live_trace(folder: Path) -> dict:
    """A run in progress, as far as it has got: the events streamed so far, and whether
    the record has landed."""
    lines = (folder / "trace.jsonl").read_text(encoding="utf-8").splitlines() \
        if (folder / "trace.jsonl").is_file() else []
    return {"label": folder.name, "events": [json.loads(line) for line in lines if line],
            "finished": (folder / "record.json").is_file(),
            "receipt": (folder / "receipt.json").is_file(),
            "running": running(folder)}


def code_version() -> str:
    """The page's code as served right now: the newest change under web/. Sent with every
    response, so a tab whose script predates it reloads once instead of running stale."""
    return str(max(p.stat().st_mtime_ns for p in WEB.iterdir() if p.is_file()))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self) -> None:
        # Nothing here may be cached: a browser showing last week's page over today's
        # archive is a stale inspector that looks current.
        self.send_header("Cache-Control", "no-store")
        self.send_header("ADII-Code", code_version())
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
            if len(parts) == 4 and parts[3] == "feedback":
                return self.send_json(feedback_of(ARCHIVE / label))
            report = ARCHIVE / label / "evaluation_report.json"
            if len(parts) == 4 and parts[3] == "evaluation" and report.is_file():
                return self.send(report.read_bytes())   # verbatim, as the authority wrote it
            record = ARCHIVE / label / "record.json"
            if len(parts) == 3 and record.is_file():
                return self.send(record.read_bytes())   # verbatim: what was archived is shown
            return self.send_json({"error": f"no run {label!r}"}, 404)
        return self.send_json({"error": "no such endpoint"}, 404)

    def body(self) -> dict:
        """The JSON object posted. ValueError for anything else — including a body not
        declared as JSON, which is how a form on some other site would arrive here."""
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            raise ValueError("send a JSON object, as application/json")
        parsed = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if not isinstance(parsed, dict):
            raise ValueError("send a JSON object, as application/json")
        return parsed

    def do_POST(self) -> None:  # noqa: N802
        """Two writes, and only two. Feedback on a run: an operator's words, kept beside the
        record. Starting a run: refused unless the operator configured a local model when
        starting the server; the label is answered at once and the run then executes in
        this request's thread while the page watches the live trace."""
        parts = self.route()
        if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "feedback":
            label = parts[2]
            if not LABEL.fullmatch(label) or not (ARCHIVE / label / "record.json").is_file():
                return self.send_json({"error": f"no finished run {label!r}"}, 404)
            try:
                return self.send_json(record_feedback(ARCHIVE / label, self.body()))
            except ValueError as why:          # not JSON, or not feedback this archive keeps
                return self.send_json({"error": str(why)}, 400)
        if parts != ["api", "runs"]:
            return self.send_json({"error": "no such endpoint"}, 404)
        if not LAUNCH:
            return self.send_json({"error": "this inspector is read-only: start it with "
                                            "--model to allow runs against a local model"}, 403)
        try:
            incident = self.body().get("incident")
        except ValueError as why:
            return self.send_json({"error": str(why)}, 400)
        if incident not in {i["incident_id"] for i in incidents()}:
            return self.send_json({"error": f"no such incident {incident!r}"}, 400)
        if any(row.get("running") for row in index(ARCHIVE)):
            return self.send_json({"error": "a run is in progress; this machine investigates "
                                            "one at a time"}, 409)
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
    print(f"ADII — http://127.0.0.1:{port}")
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
