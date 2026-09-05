"""Deliberately stupid backend for the ADII demonstration layer.

    python -m adii.demo            # http://127.0.0.1:8000

It reads JSON out of fixtures/ and serves it. That is the whole implementation.

There is no model, no SQL execution, no agent loop, and no evaluator behind these
endpoints — on purpose. The demo exists to show the SHAPE of the eventual system so
four people can see what they are building before they build it. Anything cleverer here
would be work the team is supposed to do, done in the wrong place.

Standard library only: the team repository has zero dependencies and this must not be the
thing that adds one.
"""
from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

# Data lives under 01_data/ and code under 02_src/, so the demo reaches across for
# its recorded runs and keeps its own static files beside itself.
FIXTURES = REPO / "01_data" / "demo" / "fixtures"
WEB = HERE / "web"

# Teaching order, not chronological: the duplicate pair first, because the same
# incident with two different candidate repairs is the clearest lesson in the set.
ORDER = ["duplicate-accepted", "repair-rejected", "no-repair", "escalate",
         "repair-accepted"]


def load(slug: str) -> dict | None:
    path = FIXTURES / slug / "run.json"
    if not path.is_file() or slug not in ORDER:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def index() -> list[dict]:
    """The run list. Only what a picker needs — the client fetches the rest."""
    summaries = []
    for slug in ORDER:
        run = load(slug)
        summaries.append({
            "slug": slug, "run_id": run["run_id"],
            "title": run["incident"]["title"],
            "incident_id": run["incident"]["incident_id"],
            "disposition": run["decision"]["disposition"],
            "validation": (run["validation"] or {}).get("verdict"),
        })
    return summaries


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def do_GET(self) -> None:  # noqa: N802  (stdlib naming)
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        if not path.startswith("/api/"):
            return super().do_GET()

        parts = path.strip("/").split("/")          # api / runs / <slug> / <section>
        if parts[:2] != ["api", "runs"]:
            return self.send_json({"error": "no such endpoint"}, 404)
        if len(parts) == 2:
            return self.send_json(index())

        run = load(parts[2])
        if run is None:
            return self.send_json({"error": f"no run {parts[2]!r}"}, 404)
        if len(parts) == 3:
            return self.send_json(run)
        section = parts[3]
        if section not in ("trace", "validation", "evaluation", "provenance"):
            return self.send_json({"error": f"no section {section!r}"}, 404)
        return self.send_json(run.get(section))

    def send_json(self, payload: object, status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        print(f"  {self.address_string()} {fmt % args}")


def main(port: int = 8000) -> int:
    print(f"ADII vision demo — http://127.0.0.1:{port}")
    print(f"  serving {len(ORDER)} fixture runs. No model, no database, no agent.\n")
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000))
