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

import json
import os
import re
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

WALKTHROUGH = Path(__file__).resolve().parents[3] / "01_data" / "walkthrough"

PAYLOAD = ("<img src=x onerror=\"document.title='EXECUTED'\">"
           "<script>document.title='EXECUTED'</script>")
TITLE = "ADII — Is it broken?"
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
    """The walkthrough record with the payload in every field a model could have written —
    the alert, the claim, a patch path and body, a tool name, an observation, the model id,
    the termination detail — and in the alerted metric's name, which the page draws."""
    context, run = load()
    context = IncidentContext(incident_id=context.incident_id, alert=PAYLOAD, as_of=context.as_of,
                              permitted_write_paths=context.permitted_write_paths)
    decision = replace(run.decision, root_cause_summary=PAYLOAD, patch={PAYLOAD: PAYLOAD})
    trace = run.trace + (
        TraceEvent(len(run.trace), "tool_result", {
            "call_id": "c9", "name": PAYLOAD, "status": "OK", "content": {"rows": [[PAYLOAD]]}}),
        TraceEvent(len(run.trace) + 1, "alert_observed", {
            "metric": PAYLOAD, "unit": PAYLOAD, "query": PAYLOAD, "columns": ["d", "v"],
            "rows": [["2026-01-01", 10.0], [PAYLOAD, 5.0]]}))
    record = RunRecord.from_run(label, context, run, configuration={"model": PAYLOAD},
                                origin="test")
    return replace(record, decision=decision, trace=trace, detail=PAYLOAD)


def serve(archive: Path, web: Path | None, monkeypatch) -> ThreadingHTTPServer:
    monkeypatch.setattr(server, "ARCHIVE", archive)
    if web is not None:
        monkeypatch.setattr(server, "WEB", web)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def browse(binary: str, tmp_path: Path, url: str, *more: str) -> str:
    return dump_dom([binary, "--headless=new", "--disable-gpu", "--no-sandbox",
                     "--disable-dev-shm-usage", "--hide-scrollbars", "--no-first-run",
                     f"--user-data-dir={tmp_path / 'chrome'}", *more, "--dump-dom", url])


def test_the_shipped_page_renders_model_text_as_text_and_executes_nothing(tmp_path,
                                                                           monkeypatch):
    binary = chrome()
    archive = tmp_path / "archive"
    write_record(poisoned("poison"), archive)
    httpd = serve(archive, None, monkeypatch)
    try:
        dom = browse(binary, tmp_path, f"http://127.0.0.1:{httpd.server_port}/#r/poison",
                     "--virtual-time-budget=5000")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "</html>" in dom, "Chrome produced no document within 40 s"
    head, body = dom.split("<body", 1)
    assert f"<title>{TITLE}</title>" in head, "the page's title changed: a handler executed"
    assert "<img" not in body, "the payload became an element: it was parsed as markup"
    assert "&lt;img src=x onerror=" in body, "the payload is not on the page as text"
    assert body.count("&lt;script&gt;") >= 4, "not every poisoned field reached the page"


HARNESS = """<!doctype html><meta charset="utf-8"><title>harness</title><body>
<script>
// Embeds the page at an exact CSS width, which headless Chrome's own window cannot go
// below 500. Same origin, so the inner document is readable: once the inner page has
// measured itself, its measurement and its text are copied out here, where --dump-dom
// can see them. Test scaffolding; never shipped.
const q = new URLSearchParams(location.search);
const frame = document.createElement("iframe");
frame.width = q.get("w"); frame.height = "12000"; frame.style.border = "0";
frame.setAttribute("scrolling", "no");
frame.src = "/#" + q.get("route");
document.body.append(frame);
const poll = setInterval(() => {
  const inner = frame.contentDocument && frame.contentDocument.documentElement;
  if (!inner || !inner.dataset.measured || !frame.contentDocument.querySelector("main")) return;
  clearInterval(poll);
  document.documentElement.dataset.measured = inner.dataset.measured;
  const out = document.createElement("pre"); out.id = "text";
  out.textContent = frame.contentDocument.body.textContent;
  document.body.append(out);
}, 50);
</script>"""

EXPECTED = {
    "": ("What looks wrong in your data?", "Attach CSV files", "Sample 1", "Sample 2", "Sample 3"),
    "new": ("What looks wrong in your data?", "Attach CSV files", "Sample 1"),
    "r/fix": ("Yes. Fix it.", "How ADII knows", "Proposed fix", "Independent rebuild",
              "Sign-off", "Record", "Investigated for", "Show details"),
    "r/leave": ("No. Leave it.", "How ADII knows", "No change proposed", "Sign-off"),
    "r/ended": ("The run couldn't finish.", "Nothing was changed.", "The record says"),
}


@pytest.mark.parametrize("width", [1440, 390])
@pytest.mark.parametrize("route", list(EXPECTED))
def test_every_screen_fits_the_viewport_at_desktop_and_phone_width(tmp_path, monkeypatch,
                                                                     width, route):
    """Mobile is an acceptance condition: no horizontal document overflow, and what each
    screen must say present at both widths. Measured in the browser at the exact width,
    through a same-origin harness, not asserted from CSS."""
    from .test_the_front_door_projects import recorded
    binary = chrome()
    archive = tmp_path / "archive"
    for label, record in (("fix", recorded("transform-defect")),
                          ("leave", recorded("business-changed"))):
        (archive / label).mkdir(parents=True)
        (archive / label / "record.json").write_text(json.dumps(record), encoding="utf-8")
    ended = {**recorded("cannot-decide"), "decision": None, "termination":
             "infrastructure_failure", "detail": "provider unreachable"}
    (archive / "ended").mkdir()
    (archive / "ended" / "record.json").write_text(json.dumps(ended), encoding="utf-8")
    web = tmp_path / "web"
    shutil.copytree(server.WEB, web)
    (web / "harness.html").write_text(HARNESS, encoding="utf-8")
    httpd = serve(archive, web, monkeypatch)
    url = f"http://127.0.0.1:{httpd.server_port}/harness.html?w={width}&route={route}"
    try:
        dom = browse(binary, tmp_path, url, f"--window-size={max(width + 40, 500)},900",
                     "--virtual-time-budget=15000")
        widths = re.search(r'data-measured="(\d+),(\d+)"', dom)
        if not widths:          # a launch under load, not a page defect: one more try
            dom = browse(binary, tmp_path, url, f"--window-size={max(width + 40, 500)},900",
                         "--virtual-time-budget=15000")
            widths = re.search(r'data-measured="(\d+),(\d+)"', dom)
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert widths, f"the inner page never reported its widths; dom tail: {dom[-300:]!r}"
    scroll, client = map(int, widths.groups())
    assert client == width, f"the harness did not embed the page at {width}px (got {client})"
    assert scroll <= client, f"horizontal overflow at {width}px: {scroll} > viewport {client}"
    text = dom[dom.index('<pre id="text">'):]
    for said in EXPECTED[route]:
        assert said in text, f"{said!r} missing from {route or 'the list'} at {width}px"
    # the history is a sidebar, open on a desk and closed on a phone until asked for
    assert (("New investigation" in text) == (width > 900)), "the sidebar's default is wrong"
    if route in ("", "new"):    # a room sees no earlier answer before the live one,
                                # the sidebar's history included: titles, never answers
        for answer in ("Fix it", "Leave it", "Escalate it", "No answer"):
            assert answer not in text, f"the launch view shows an earlier {answer!r}"
    assert "could not be read" not in text, "the page rendered an error state"
