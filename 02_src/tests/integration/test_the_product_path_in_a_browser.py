"""The product path a stranger takes, driven in a real browser: Investigate a known incident,
watch it run, read the story, leave feedback — against a stand-in model, spending nothing.

The server side of each step is pinned in test_inspector_serves_the_archive.py. This test
is the receipt for the seam between them: the shipped page, in Chrome, does all of it in
one sitting, and the record it read before feedback is the record it reads after.
"""
from __future__ import annotations

import json
import re
import shutil
import threading
from http.server import ThreadingHTTPServer

from adii.demo import server

from .fake_model import FakeModel
from .test_the_page_executes_nothing import chrome, dump_dom

# A same-origin harness: the inspector in an iframe, scripted from outside the way a person
# would use it, and what it showed at each step copied out where --dump-dom can see it.
# Every await is preceded by a step change, so a tick that fires meanwhile does nothing twice.
# Under a virtual-time budget every 1 s poll the page makes costs 1 s of budget in about a
# millisecond of real time, so the budget below is sized in polls, not seconds.
FLOW = """<!doctype html><meta charset="utf-8"><title>flow</title><body>
<script>
const frame = document.createElement("iframe");
frame.width = "1200"; frame.height = "12000"; frame.style.border = "0";
frame.src = "/#";
document.body.append(frame);
const out = (k, v) => { document.documentElement.dataset[k] = v; };
const seen = new Set(); let step = "boot"; let label = null; let before = null;
const go = (next) => { step = next; out("step", next); };
const record = async () => (await fetch("/api/runs/" + encodeURIComponent(label))).text();
const tick = setInterval(async () => {
  const doc = frame.contentDocument;
  if (!doc || !doc.body) return;
  const text = doc.body.textContent;
  if (text.includes("Starting")) seen.add("starting");
  if (text.includes("Investigating")) seen.add("running");
  if (step === "boot") {
    const select = doc.getElementById("launch-incident");
    if (!select || !select.options.length) return;
    select.value = "orders-missing-day";
    go("launched");
    doc.querySelector("button.adii-btn--primary").click();
  } else if (step === "launched") {
    if (!frame.contentWindow.location.hash.startsWith("#r/")) return;
    label = decodeURIComponent(frame.contentWindow.location.hash.slice(3));
    out("label", label);
    go("watching");
  } else if (step === "watching") {
    const story = (text.includes("Decided: ") || text.includes("Stopped ")) &&
      text.includes("Record feedback");
    if (!story) return;
    go("reading");
    before = await record();
    doc.querySelector('input[name="useful"][value="partly"]').click();
    doc.querySelector("textarea.adii-input").value = "why it stopped";
    doc.querySelector("input.adii-input").value = "Sam";
    go("feedback");
    [...doc.querySelectorAll("button")].find((b) => b.textContent === "Record feedback").click();
  } else if (step === "feedback") {
    if (!text.includes("Feedback recorded")) return;
    go("checking");
    const after = await record();
    out("unchanged", String(before.length > 0 && after === before));
    out("seen", [...seen].sort().join(","));
    const pre = document.createElement("pre"); pre.id = "text"; pre.textContent = text;
    document.body.append(pre);
    clearInterval(tick);
    go("done");
  }
}, 200);
</script>"""


def test_a_stranger_starts_watches_reads_and_answers_a_run_in_the_browser(tmp_path,
                                                                           monkeypatch):
    binary = chrome()
    FakeModel.script[:] = [
        '<TOOL_CALL>{"name": "get_schema", "arguments": {"table": "orders"}}',
        '<DECISION>{"disposition": "ESCALATE", "root_cause_id": null, '
        '"root_cause_summary": "not enough here", "repair_id": null, "patch": {}}']
    FakeModel.delay = 0.2                     # two turns: long enough to be seen running
    model = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    archive = tmp_path / "archive"
    archive.mkdir()
    web = tmp_path / "web"
    shutil.copytree(server.WEB, web)
    (web / "flow.html").write_text(FLOW, encoding="utf-8")
    monkeypatch.setattr(server, "ARCHIVE", archive)
    monkeypatch.setattr(server, "WEB", web)
    monkeypatch.setattr(server, "LAUNCH", {
        "endpoint": f"http://127.0.0.1:{model.server_port}/v1", "model": "test-model-1",
        "served_as": None, "max_turns": 6})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        dom = dump_dom(
            [binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
             "--hide-scrollbars", "--no-first-run", f"--user-data-dir={tmp_path / 'chrome'}",
             "--window-size=1280,900", "--virtual-time-budget=36000000", "--dump-dom",
             f"http://127.0.0.1:{httpd.server_port}/flow.html"])
    finally:
        httpd.shutdown()
        httpd.server_close()
        model.shutdown()
        model.server_close()
        FakeModel.delay = 0.0
    assert "</html>" in dom, f"no document within the deadline; dom tail: {dom[-300:]!r}"
    flow = dict(re.findall(r'data-([a-zA-Z]+)="([^"]*)"', dom.split("<body", 1)[0]))
    assert flow.get("step") == "done", f"the flow stopped at {flow.get('step')!r}: {flow}"
    label = flow["label"]
    assert label.startswith("orders-missing-day-")
    # watched, not just shown the end. ("Starting…" lasts only from the click to the
    # navigation, so whether a tick lands in that window is timing, not a property.)
    assert "running" in flow["seen"].split(","), flow
    assert flow["unchanged"] == "true"
    text = dom[dom.index('<pre id="text">'):]
    assert "Decided: ESCALATE" in text and "What it concluded" in text
    assert "The investigation, turn by turn" in text and "One investigation at a time." in text
    assert "Sam" in text and "why it stopped" in text     # shown back, verbatim
    assert "did not load" not in text
    kept = (archive / label / "feedback.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["by"] for line in kept] == ["Sam"]
    assert (archive / label / "receipt.json").is_file()
    assert json.loads((archive / label / "record.json").read_text(encoding="utf-8"))["decision"][
        "disposition"] == "ESCALATE"
