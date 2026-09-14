"""Inherited D12, in a browser: the shipped page renders what a model wrote as text, and no
handler executes.

The source-level rule in test_demo_design_rules.py forbids every known door from string to
markup. This test drives the shipped rendering code in a real engine and watches what
happens, which is the only check that goes red when an escape is reverted in a way no grep
anticipated. A payload that executes the moment it is parsed as markup is put in every
model-written field of a record; the page must show it as text and its own title must
survive.

Chrome is found by ADII_CHROME, on PATH, or where the operating system installs it. Absent
locally the test skips and says so. On CI absence fails: every runner the team uses ships
Chrome, and a skipped browser check is a check nobody ran.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from adii.contracts import IncidentContext, TraceEvent
from adii.demo import server
from adii.examples.walkthrough import load
from adii.reporting import RunRecord, write_record

PAYLOAD = ("<img src=x onerror=\"document.title='EXECUTED'\">"
           "<script>document.title='EXECUTED'</script>")
TITLE = "ADII — Run inspector"
INSTALLED = {
    "darwin": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
    "win32": [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"],
}


def chrome() -> str:
    on_path = (shutil.which(name) for name in
               ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"))
    installed = (p for p in INSTALLED.get(sys.platform, []) if Path(p).is_file())
    found = os.environ.get("ADII_CHROME") or next(filter(None, on_path), None) \
        or next(installed, None)
    if found:
        return found
    if os.environ.get("CI"):
        pytest.fail("no Chrome on this CI runner: the browser check did not run")
    pytest.skip("no Chrome found; set ADII_CHROME to run the browser check")


def dump_dom(command: list[str]) -> str:
    """Chrome's --dump-dom writes the document once the virtual-time budget has let every
    fetch finish — and then, on some builds, never exits. So the output is read as it comes
    and the process is killed the moment the closing tag has arrived."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace")
    lines: list[str] = []
    threading.Thread(target=lambda: lines.extend(proc.stdout), daemon=True).start()
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline and not any("</html>" in line for line in lines[-3:]):
        time.sleep(0.1)
    proc.kill()
    proc.wait()
    return "".join(lines)


def poisoned(label: str) -> RunRecord:
    """The walkthrough record with the payload in every field a model could have written:
    the alert, the claim, a patch path and body, a tool name, an observation, the model id,
    the termination detail."""
    context, run = load()
    context = IncidentContext(incident_id=context.incident_id, alert=PAYLOAD, as_of=context.as_of,
                              permitted_write_paths=context.permitted_write_paths)
    decision = replace(run.decision, root_cause_summary=PAYLOAD, patch={PAYLOAD: PAYLOAD})
    trace = run.trace + (TraceEvent(len(run.trace), "tool_result", {
        "call_id": "c9", "name": PAYLOAD, "status": "OK", "content": {"rows": [[PAYLOAD]]}}),)
    record = RunRecord.from_run(label, context, run, configuration={"model": PAYLOAD},
                                origin="test")
    return replace(record, decision=decision, trace=trace, detail=PAYLOAD)


def test_the_shipped_page_renders_model_text_as_text_and_executes_nothing(tmp_path,
                                                                           monkeypatch):
    binary = chrome()
    archive = tmp_path / "archive"
    monkeypatch.setattr(server, "ARCHIVE", archive)
    write_record(poisoned("poison"), archive)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        dom = dump_dom(
            [binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
             "--hide-scrollbars", "--no-first-run", f"--user-data-dir={tmp_path / 'chrome'}",
             "--virtual-time-budget=5000", "--dump-dom",
             f"http://127.0.0.1:{httpd.server_port}/#poison"])
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "</html>" in dom, "Chrome produced no document within 40 s"
    head, body = dom.split("<body", 1)
    assert f"<title>{TITLE}</title>" in head, "the page's title changed: a handler executed"
    assert "<img" not in body, "the payload became an element: it was parsed as markup"
    assert "&lt;img src=x onerror=" in body, "the payload is not on the page as text"
    assert body.count("&lt;script&gt;") >= 4, "not every poisoned field reached the page"
