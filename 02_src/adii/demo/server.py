"""The product's backend: serves the run archive to the browser, and, when the operator
says so, starts a run — on the visitor's own incident over their files, or on one of the
archive's — against the provider the operator configured.

    python -m adii.demo                                  # read-only: the archive, nothing else
    python -m adii.demo 8000 --endpoint http://127.0.0.1:8090/v1 \\
        --model Qwen3-4B-Instruct-2507-4bit --served-as default_model    # and live runs
    python -m adii.demo 8000 --provider openai --model gpt-4.1 \\
        --max-cost-usd 0.25 --max-turns 20         # paid runs; OPENAI_API_KEY in this process
                                                  # (+ --max-tool-calls, --max-model-requests,
                                                  #  --max-wall-clock-seconds: every runtime bound)

Read-only by default: it lists `01_data/runs/<label>/record.json`, serves each record
verbatim, and serves the static page. A page that can start a run can spend money and
create a first exposure, so launching exists only when the person at the terminal
configured a model. The browser chooses the incident and, within the flags the server was
started with, a priced model, a cap and a turn budget — requests the server checks and
refuses when they exceed its own, never clamps; provider, endpoint and credential are the
server's alone. Every run is forwarded to the same `python -m adii.runtime` entry point
the command line uses. A paid provider is reachable
only when the operator said so at startup, with the credential already in this process's
environment and checked before the port was bound; it goes from there to the wire and to
nothing the page can read — the runtime's paid path owns that, and its tests hold it.

Standard library only: the team repository has zero dependencies and this must not be the
thing that adds one. A launched run executes inside the request that started it, in the
server's own process, and the page watches it through the live trace on other connections;
the response is sent first, so the browser is never held. One run at a time: a second is
refused while the archive shows one running.
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import time
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..examples.canonical_world import DEMO, DEMO_STATES, INCIDENTS, incident_id
from ..examples.specimens import SPECIMENS
from ..examples.walkthrough import load as load_walkthrough
from ..reporting.ledger import PRICES
from ..reporting.record import ARCHIVE, LABEL, REPO, read_record
from ..runtime.__main__ import alerted_series
from ..runtime.__main__ import main as run_main
from ..tools import ReadOnlyDatabase
from ..tools.user_world import LIMITS, world_from_files

WEB = Path(__file__).resolve().parent / "web"

# Set from the command line: the runtime's own flags, as the operator gave them — each
# run's default, and the ceiling a request from the page may not pass. Empty means
# read-only: the page can start nothing. Never a credential.
LAUNCH: dict[str, object] = {}
# A run whose live trace has not moved for this long is not running; it died.
STALE_AFTER_S = 180
# One run at a time in this process too: the archive shows a run only once the runtime has
# reserved its folder, a moment after the label was answered — two requests in that moment
# would both start, and on the paid path both would spend.
RUNNING = threading.Lock()


def models() -> list[str]:
    """The models a run may be asked for: on the paid path every priced one — the price
    table is the allow-list, and the cap bounds the spend whichever is chosen; on a local
    endpoint only the one the operator named, since the page cannot know what it serves."""
    if LAUNCH.get("provider") == "openai" and not LAUNCH.get("reasoning_effort"):
        return sorted(PRICES)
    return [str(LAUNCH["model"])]     # a reasoning effort is the operator's model's setting


def requested(body: dict) -> dict[str, object]:
    """The run settings the page asked for, each checked against the operator's — requests,
    not authority: a model the server offers, a turn budget and a cap at most the server's
    own. Absent, the server's. ValueError names the refusal; nothing is clamped, so a run
    that exists ran exactly what was asked."""
    model, turns = body.get("model", LAUNCH["model"]), body.get("max_turns", LAUNCH["max_turns"])
    if model not in models():
        raise ValueError(f"model must be one of {', '.join(models())}")
    if not (isinstance(turns, int) and not isinstance(turns, bool)
            and 1 <= turns <= int(LAUNCH["max_turns"])):
        raise ValueError(f"max_turns must be a whole number from 1 to {LAUNCH['max_turns']}")
    chosen: dict[str, object] = {"model": model, "max_turns": turns}
    if LAUNCH.get("provider") == "openai":
        ceiling = float(LAUNCH["max_cost_usd"])
        cost = body.get("max_cost_usd", ceiling)
        # the ceiling is finite (checked at startup), so inf and nan both fail this
        if not (isinstance(cost, (int, float)) and not isinstance(cost, bool)
                and 0 < cost <= ceiling):
            raise ValueError(f"max_cost_usd must be above zero and at most {ceiling}")
        chosen["max_cost_usd"] = cost
    elif "max_cost_usd" in body:
        raise ValueError("max_cost_usd applies to a paid provider only; nothing is spent here")
    return chosen


# An incident the visitor brings: what looks wrong, in their words, over their own files.
BROUGHT = {"description": 2000, "body": 12_000_000}


def brought(body: dict) -> tuple[dict, str]:
    """The visitor's own incident from the posted JSON: `description` (what looks wrong —
    the alert the investigator is told) and `files` (CSV name and contents, one table each)
    become the incident.json and world.sql the runtime loads. The id is the digest of both,
    so the same question over the same data is the same incident, run again. ValueError
    names what this page will not take; nothing is written."""
    description, files = body.get("description"), body.get("files")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("say what looks wrong: description is the alert the investigator is told")
    if len(description) > BROUGHT["description"]:
        raise ValueError(f"description is limited to {BROUGHT['description']} characters")
    if not (isinstance(files, list) and 1 <= len(files) <= LIMITS["files"] and all(
            isinstance(f, dict) and isinstance(f.get("name"), str)
            and isinstance(f.get("text"), str) for f in files)):
        raise ValueError(f"files: 1 to {LIMITS['files']} CSV files, each as its name and its text")
    world = world_from_files([(f["name"], f["text"]) for f in files])       # ValueError: the reason
    ReadOnlyDatabase.in_memory(world)       # and it builds: proved here, before a label is answered
    digest = hashlib.sha256((description.strip() + "\n" + world).encode("utf-8")).hexdigest()
    incident = {"incident_id": f"upload-{digest[:10]}", "alert": description.strip(),
                "as_of": datetime.now(UTC).isoformat(timespec="seconds"),
                "permitted_write_paths": []}
    return incident, world


# the samples the page offers a first visitor: the company generated for the stage
SAMPLES = tuple(incident_id(DEMO, state) for state in DEMO_STATES)


def incidents() -> list[dict[str, object]]:
    """Every incident a run can be started on: the walkthrough's, the development packages'
    and the specimens'. A sample carries its alerted series, read from its world the way
    the runtime reads it, so the page can draw what looks wrong before anything runs."""
    context, _ = load_walkthrough()
    packages = [json.loads((p / "incident.json").read_text(encoding="utf-8"))
                for p in sorted(INCIDENTS.glob("*")) if (p / "incident.json").is_file()]
    return [{"incident_id": context.incident_id, "alert": context.alert},
            *({"incident_id": p["incident_id"], "alert": p["alert"],
               **({"sample": True, "series": alerted_series(INCIDENTS / p["incident_id"])}
                  if p["incident_id"] in SAMPLES else {})} for p in packages),
            *({"incident_id": s.context.incident_id, "alert": s.context.alert}
              for s in SPECIMENS)]


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
            "alert": record.context.alert,
            "changed": sorted(record.decision.patch) if record.decision else [],
            "admissible": record.admissible,
            "termination": record.termination,
            "disposition": record.decision.disposition.value if record.decision else None,
            # the contract's own derivation: ACCEPT, REJECT, NOT_CHECKABLE, or the legacy
            # UNCHECKED of records written before 22 September
            "validation": None if record.validation is None else record.validation.state,
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
            return self.send_json({"enabled": bool(LAUNCH), **LAUNCH,
                                   **({"models": models()} if LAUNCH else {})})
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

    def body(self, limit: int = 65_536) -> dict:
        """The JSON object posted. ValueError for anything else — including a body not
        declared as JSON, which is how a form on some other site would arrive here — and
        for a body above `limit`, refused before it is read."""
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            raise ValueError("send a JSON object, as application/json")
        length = int(self.headers.get("Content-Length", 0))
        if length > limit:
            raise ValueError(f"the body is limited to {limit:,} bytes")
        parsed = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(parsed, dict):
            raise ValueError("send a JSON object, as application/json")
        return parsed

    def do_POST(self) -> None:  # noqa: N802
        """Three writes, and only three. Feedback on a run: an operator's words, kept beside
        the record. Starting a run — on an incident the archive knows, or on the visitor's
        own over their files: refused unless the operator configured a model when starting
        the server; the page may ask for a model, a cap and a turn budget within the
        operator's; the label is answered at once and the run then executes in this
        request's thread — the runtime's command, the server's flags with the page's
        requests over them — while the page watches the live trace."""
        parts = self.route()
        if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "feedback":
            label = parts[2]
            if not LABEL.fullmatch(label) or not (ARCHIVE / label / "record.json").is_file():
                return self.send_json({"error": f"no finished run {label!r}"}, 404)
            try:
                return self.send_json(record_feedback(ARCHIVE / label, self.body()))
            except ValueError as why:          # not JSON, or not feedback this archive keeps
                return self.send_json({"error": str(why)}, 400)
        if parts not in (["api", "runs"], ["api", "investigations"]):
            return self.send_json({"error": "no such endpoint"}, 404)
        if not LAUNCH:
            return self.send_json({"error": "this inspector is read-only: start it with "
                                            "--model to allow runs from the page"}, 403)
        try:
            if parts == ["api", "runs"]:                # an incident the archive knows
                body = self.body()
                incident = body.get("incident")
                if not isinstance(incident, str) \
                        or incident not in {i["incident_id"] for i in incidents()}:
                    raise ValueError(f"no such incident {incident!r}")
                return self.launch(incident, requested(body))
            body = self.body(limit=BROUGHT["body"])     # the visitor's own, over their files
            incident, world = brought(body)
            chosen = requested(body)
        except ValueError as why:            # not JSON, not an incident, or more than allowed
            return self.send_json({"error": str(why)}, 400)
        with tempfile.TemporaryDirectory() as staging:   # gone once the runtime has kept both
            folder = Path(staging)
            (folder / "incident.json").write_text(json.dumps(incident, indent=2), encoding="utf-8")
            (folder / "world.sql").write_text(world, encoding="utf-8")
            return self.launch(incident["incident_id"], chosen, folder)

    def launch(self, incident_id: str, chosen: dict, folder: Path | None = None) -> None:
        """One run, from the archive's incident or the visitor's folder: the label answered
        at once, then the runtime's command in this thread with the server's flags and the
        page's requests over them."""
        busy = {"error": "a run is in progress; this machine investigates one at a time"}
        if any(row.get("running") for row in index(ARCHIVE)) or not RUNNING.acquire(blocking=False):
            return self.send_json(busy, 409)
        try:
            now = datetime.now(UTC)
            label = f"{incident_id}-{now:%Y%m%dT%H%M%S}-{now.microsecond // 1000:03d}Z"
            self.send_json({"label": label})          # the page navigates and starts watching
            self.wfile.flush()
            ceilings = ", ".join([
                f"{LAUNCH['max_turns']} turns",
                *(f"{LAUNCH[key]:g} {unit}" for key, unit in (
                    ("max_tool_calls", "tool calls"), ("max_model_requests", "requests"),
                    ("max_wall_clock_seconds", "s")) if key in LAUNCH),
                *([f"up to ${float(LAUNCH['max_cost_usd']):.2f}"] if "max_cost_usd" in LAUNCH
                  else [])])
            run_main([*(["--incident-dir", str(folder)] if folder else ["--incident", incident_id]),
                      "--label", label, "--no-report", "--archive", str(ARCHIVE),
                      "--requested-from", f"the page, within the ceilings the operator set when "
                                          f"starting the server ({ceilings})",
                      *(flag for key, value in {**LAUNCH, **chosen}.items() if value is not None
                        for flag in (f"--{key.replace('_', '-')}", str(value)))])
        finally:
            RUNNING.release()

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
    if LAUNCH.get("provider") == "openai":
        print(f"Runs may be started from the page, against {LAUNCH['model']} by default — any "
              f"priced model on request — at {LAUNCH['endpoint']}, a paid provider, up to "
              f"${LAUNCH['max_cost_usd']:.2f} per run at nominal prices, a hard cap; the "
              "credential is this process's, from its environment.")
    elif LAUNCH:
        print(f"Runs may be started from the page, against {LAUNCH['model']} at "
              f"{LAUNCH['endpoint']} — a local endpoint, nothing is spent.")
    else:
        print("Read-only: start with --model to allow runs from the page.")
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
