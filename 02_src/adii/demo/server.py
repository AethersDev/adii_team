"""The inspector's backend: serves the run archive to the browser, read-only.

    python -m adii.demo            # http://127.0.0.1:8000

It lists `01_data/runs/<label>/record.json`, serves each record verbatim, and serves the
static page. That is the whole implementation, on purpose: a browser must never be able to
spend money or create a first exposure, so runs are launched from the command line and
this process only reads what they archived.

Standard library only: the team repository has zero dependencies and this must not be the
thing that adds one.
"""
from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..reporting.record import ARCHIVE, LABEL, REPO, read_record

WEB = Path(__file__).resolve().parent / "web"


def index(root: Path) -> list[dict]:
    """One row per archived run, newest first — only what a run list needs. A record this
    reader cannot load is listed with its error rather than hidden: an archive that quietly
    drops a run is worse than one that shows a broken one."""
    rows = []
    for folder in root.glob("*"):
        if not folder.is_dir():                   # the README beside the runs
            continue
        label, path = folder.name, folder / "record.json"
        if not path.is_file():
            rows.append({"label": label, "error": "the label was reserved but no record was "
                                                  "written; the run did not finish"})
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
    rows.sort(key=lambda row: row.get("written_at") or "", reverse=True)
    return rows


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self) -> None:
        # Nothing here may be cached: a browser showing last week's page over today's
        # archive is a stale inspector that looks current.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:  # noqa: N802  (stdlib naming)
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if not path.startswith("/api/"):
            return super().do_GET()
        parts = path.strip("/").split("/")          # api / runs / <label>
        if parts[:2] != ["api", "runs"] or len(parts) > 3:
            return self.send_json({"error": "no such endpoint"}, 404)
        if len(parts) == 2:
            return self.send_json(index(ARCHIVE))
        label = parts[2]
        record = ARCHIVE / label / "record.json"
        # LABEL first: a label that is not one path segment never reaches the filesystem,
        # where a backslash is a directory separator on Windows.
        if not LABEL.fullmatch(label) or not record.is_file():
            return self.send_json({"error": f"no run {label!r}"}, 404)
        return self.send(record.read_bytes())      # verbatim: what was archived is what is shown

    def send_json(self, payload: object, status: int = 200) -> None:
        self.send(json.dumps(payload, indent=2, allow_nan=False).encode("utf-8"), status)

    def send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.address_string()} {fmt % args}")


def main(port: int = 8000) -> int:
    runs = index(ARCHIVE)
    print(f"ADII run inspector — http://127.0.0.1:{port}")
    print(f"  {len(runs)} archived run(s) in {ARCHIVE.relative_to(REPO)}. Read-only.")
    if not runs:
        print("  Produce one now:  python -m adii.runtime --incident demo-learning-001 "
              "--provider fake")
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


if __name__ == "__main__":
    import sys
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000))
