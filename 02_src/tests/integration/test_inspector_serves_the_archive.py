"""The inspector is read-only over the archive, and an archive that hides a broken run is
worse than one that shows it."""
from __future__ import annotations

import http.client
import json
import os
import socket
import threading
import time
from http.server import ThreadingHTTPServer

from adii.demo import server
from adii.demo.server import index, main
from adii.examples.walkthrough import main as walkthrough


def test_an_empty_archive_lists_nothing(tmp_path):
    assert index(tmp_path) == []


def test_an_archived_run_is_listed_with_what_a_run_list_needs(tmp_path):
    assert walkthrough(["--archive", str(tmp_path)]) == 0
    [row] = index(tmp_path)
    assert row["label"] == "demo-learning-001"
    assert row["termination"] == "submitted"
    assert row["disposition"] == "REPAIR" and row["validation"] == "ACCEPT"
    assert row["provider"] == "fixture" and row["model"] is None
    assert row["api_cost_usd"] == 0.0142 and row["written_at"]


def test_an_unreadable_record_is_listed_not_hidden(tmp_path):
    """Two ways a file is unreadable — the wrong schema, and the right schema over the wrong
    shape — and both list with their error. One broken file never takes the listing down."""
    assert walkthrough(["--archive", str(tmp_path)]) == 0
    doc = json.loads((tmp_path / "demo-learning-001" / "record.json").read_text(encoding="utf-8"))
    doc["trace"] = "oops"
    (tmp_path / "shape").mkdir()
    (tmp_path / "shape" / "record.json").write_text(json.dumps(doc), encoding="utf-8")
    (tmp_path / "version").mkdir()
    (tmp_path / "version" / "record.json").write_text(
        '{"schema": "adii.run_record/v9"}', encoding="utf-8")
    rows = {row["label"]: row for row in index(tmp_path)}
    assert "malformed" in rows["shape"]["error"]
    assert "unknown record schema" in rows["version"]["error"]
    assert rows["demo-learning-001"]["disposition"] == "REPAIR"


def test_a_reserved_label_without_a_record_is_listed_not_hidden(tmp_path):
    """A run killed between claiming its label and writing its record leaves an empty
    folder. That is a run that happened, so it is listed as one that did not finish. Files
    beside the runs — the README — are not runs."""
    (tmp_path / "killed").mkdir()
    (tmp_path / "README.md").write_text("the archive", encoding="utf-8")
    (tmp_path / "receipted").mkdir()
    (tmp_path / "receipted" / "receipt.json").write_text("{}", encoding="utf-8")
    (tmp_path / "died").mkdir()
    (tmp_path / "died" / "receipt.json").write_text("{}", encoding="utf-8")
    (tmp_path / "died" / "trace.jsonl").write_text("{}\n", encoding="utf-8")
    old = time.time() - server.STALE_AFTER_S - 1
    os.utime(tmp_path / "died" / "trace.jsonl", (old, old))
    (tmp_path / "going").mkdir()
    (tmp_path / "going" / "receipt.json").write_text("{}", encoding="utf-8")
    (tmp_path / "going" / "trace.jsonl").write_text("{}\n", encoding="utf-8")
    rows = {row["label"]: row for row in index(tmp_path)}
    assert "no record was written" in rows["killed"]["error"]
    assert "a receipt was written, but no record" in rows["receipted"]["error"]
    assert "a live trace were written, but no record" in rows["died"]["error"]
    assert rows["going"]["running"] is True and rows["going"]["error"] is None


def test_the_server_serves_the_archive_verbatim_uncached_and_nothing_else(tmp_path, monkeypatch):
    """The HTTP layer end to end: the list, the record byte for byte, the page, no caching,
    and a label that is not one path segment never reaching the filesystem — on Windows a
    backslash walks up a directory, and the record next door is not the archive's."""
    archive = tmp_path / "archive"
    monkeypatch.setattr(server, "ARCHIVE", archive)
    assert walkthrough(["--archive", str(archive)]) == 0
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "record.json").write_text("{}", encoding="utf-8")
    # A folder that exists but is not a label: only the label rule can refuse it, on every
    # platform. Without that rule the file below would be served.
    (archive / ".hidden").mkdir()
    (archive / ".hidden" / "record.json").write_bytes(
        (archive / "demo-learning-001" / "record.json").read_bytes())
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=5)

        def get(path):
            conn.request("GET", path)
            response = conn.getresponse()
            return response, response.read()

        listing, body = get("/api/runs")
        assert listing.status == 200 and listing.getheader("Cache-Control") == "no-store"
        rows = {row["label"]: row for row in json.loads(body)}
        assert set(rows) == {"demo-learning-001", ".hidden"}
        assert rows[".hidden"]["error"] == "the folder's name is not a label"
        _, body = get("/api/runs/demo-learning-001")
        assert body == (archive / "demo-learning-001" / "record.json").read_bytes()
        page, _ = get("/")
        assert page.status == 200 and page.getheader("Cache-Control") == "no-store"
        for path in ("/api/runs/..\\outside", "/api/runs/../outside", "/api/runs/nope",
                     "/api/nope", "/api/runs/.hidden"):
            assert get(path)[0].status == 404, path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_taken_port_is_a_message_not_a_traceback(capsys):
    """The most common way to start the inspector twice. It has to say which port and what
    to type, not dump socketserver's stack."""
    with socket.socket() as held:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):   # on Windows a second bind can steal a port
            held.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        assert main(port) == 1
    out = capsys.readouterr().out
    assert f"could not listen on 127.0.0.1:{port}" in out
    assert f"python -m adii.demo {port + 1}" in out


def test_a_run_can_be_started_from_the_page_only_when_the_operator_allowed_it(tmp_path,
                                                                              monkeypatch):
    """Read-only by default: POST is refused. Started with a local model: POST answers a
    label at once, the receipt and the live trace appear while the run executes, and the
    record lands — the same adii.run_record/v1 the command line writes."""
    from .fake_model import FakeModel
    FakeModel.script[:] = [
        '<TOOL_CALL>{"name": "get_schema", "arguments": {"table": "orders"}}',
        '<DECISION>{"disposition": "ESCALATE", "root_cause_id": null, '
        '"root_cause_summary": "not enough here", "repair_id": null, "patch": {}}']
    model = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    archive = tmp_path / "archive"
    archive.mkdir()
    monkeypatch.setattr(server, "ARCHIVE", archive)
    monkeypatch.setattr(server, "LAUNCH", {})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        def call(method, path, body=None):
            conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=30)
            conn.request(method, path, body=json.dumps(body) if body else None,
                         headers={"Content-Type": "application/json"} if body else {})
            response = conn.getresponse()
            return response.status, json.loads(response.read() or b"{}")

        status, answer = call("POST", "/api/runs", {"incident": "orders-missing-day"})
        assert status == 403 and "read-only" in answer["error"]
        assert call("GET", "/api/launch")[1] == {"enabled": False}
        assert [i["incident_id"] for i in call("GET", "/api/incidents")[1]][:2] == \
            ["demo-learning-001", "orders-missing-day"]

        server.LAUNCH.update({"endpoint": f"http://127.0.0.1:{model.server_port}/v1",
                              "model": "test-model-1", "served_as": None, "max_turns": 6})
        assert call("GET", "/api/launch")[1]["enabled"] is True
        assert call("POST", "/api/runs", {"incident": "nope"})[0] == 400
        status, answer = call("POST", "/api/runs", {"incident": "orders-missing-day"})
        assert status == 200 and answer["label"].startswith("orders-missing-day-")
        label = answer["label"]
        deadline = time.time() + 30
        while time.time() < deadline:
            status, live = call("GET", f"/api/runs/{label}/trace")
            if status == 200 and live["finished"]:
                break
            time.sleep(0.2)
        assert live["finished"] and live["receipt"]
        assert [e["kind"] for e in live["events"]][:3] == \
            ["incident_received", "model_requested", "model_responded"]
        status, record = call("GET", f"/api/runs/{label}")
        assert status == 200 and record["decision"]["disposition"] == "ESCALATE"
        assert record["configuration"]["model"] == "test-model-1"
        assert (archive / label / "receipt.json").is_file()
    finally:
        httpd.shutdown()
        httpd.server_close()
        model.shutdown()
        model.server_close()
