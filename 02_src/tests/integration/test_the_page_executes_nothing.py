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
             f"http://127.0.0.1:{httpd.server_port}/#r/poison"])
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
// Embeds the inspector at an exact CSS width, which headless Chrome's own window cannot go
// below 500. Same origin, so the inner document is readable: once the inner page has
// measured itself, its measurement and its text are copied out here, where --dump-dom
// can see them. Test scaffolding; never shipped.
const q = new URLSearchParams(location.search);
const frame = document.createElement("iframe");
frame.width = q.get("w"); frame.height = "2400"; frame.style.border = "0";
frame.src = "/#" + q.get("route");
document.body.append(frame);
const poll = setInterval(() => {
  const inner = frame.contentDocument && frame.contentDocument.documentElement;
  if (!inner || !inner.dataset.measured) return;
  clearInterval(poll);
  document.documentElement.dataset.measured = inner.dataset.measured;
  const out = document.createElement("pre"); out.id = "text";
  out.textContent = frame.contentDocument.body.textContent;
  document.body.append(out);
}, 50);
</script>"""


@pytest.mark.parametrize(("width", "route"), [
    (1440, "r/accepted"), (1440, "r/bound-hit"), (1440, ""),
    (390, "r/accepted"), (390, "r/bound-hit"), (390, ""),
])
def test_every_screen_fits_the_viewport_at_desktop_and_phone_width(tmp_path, monkeypatch,
                                                                     width, route):
    """Mobile is an acceptance condition: no horizontal document overflow, and the sections
    a stranger needs — what was reported, how the run ended, the steps, the decision or its
    absence, how to create a run — present at both widths. Measured in the browser at the
    exact width, through a same-origin harness, not asserted from CSS."""
    binary = chrome()
    archive = tmp_path / "archive"
    for label, source in (("accepted", WALKTHROUGH / "record.json"),
                          ("bound-hit", WALKTHROUGH / "endings" / "bound-hit" / "record.json")):
        (archive / label).mkdir(parents=True)
        (archive / label / "record.json").write_bytes(source.read_bytes())
    web = tmp_path / "web"
    shutil.copytree(server.WEB, web)
    (web / "harness.html").write_text(HARNESS, encoding="utf-8")
    monkeypatch.setattr(server, "ARCHIVE", archive)
    monkeypatch.setattr(server, "WEB", web)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        dom = dump_dom(
            [binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
             "--hide-scrollbars", "--no-first-run", f"--user-data-dir={tmp_path / 'chrome'}",
             f"--window-size={max(width + 40, 500)},900", "--virtual-time-budget=15000",
             "--dump-dom",
             f"http://127.0.0.1:{httpd.server_port}/harness.html?w={width}&route={route}"])
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "</html>" in dom
    widths = re.search(r'data-measured="(\d+),(\d+)"', dom)
    assert widths, "the inner page never reported its measured widths"
    scroll, client = map(int, widths.groups())
    assert client == width, f"the harness did not embed the page at {width}px (got {client})"
    assert scroll <= client, f"horizontal overflow at {width}px: {scroll} > viewport {client}"
    text = dom[dom.index('<pre id="text">'):]
    if route:
        for heading in ("What was reported", "How the run ended", "What the investigator did"):
            assert heading in text, f"{heading!r} missing at {width}px"
        assert ("What it decided" in text) != ("Why there is no decision" in text)
        assert "Creating a run" in text
    else:
        assert "Autonomous Data Incident Investigator" in text and "Incidents" in text
        assert "View the investigation history" in text
