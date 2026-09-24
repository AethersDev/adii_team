"""The product path a stranger takes, driven in a real browser against a stand-in model,
spending nothing: the front door's two entries, each through the same runtime, tools,
authorizer and validator the evaluation uses.

A sample incident: pick it on an empty workspace, Investigate, watch it run, read the
answer — here the demo company's broken staging change, repaired, permitted and accepted by
the real validator's rebuild. And the visitor's own data: say what looks wrong, attach a
CSV, Investigate, read the answer. In both, what the page showed is what the archive holds.
"""
from __future__ import annotations

import json
import re
import shutil
import threading
from http.server import ThreadingHTTPServer

from adii.demo import server
from adii.examples.canonical_world import DEMO, STG, incident_id

from .fake_model import FakeModel
from .test_the_page_executes_nothing import chrome, dump_dom

SAMPLE = incident_id(DEMO, "transform-defect")

# A same-origin harness: the page in an iframe, used from outside the way a person would,
# and what it showed copied out where --dump-dom can see it. Each await is preceded by a
# step change, so a tick that fires meanwhile does nothing twice.
FLOW = """<!doctype html><meta charset="utf-8"><title>flow</title><body>
<script>
const frame = document.createElement("iframe");
frame.width = "1440"; frame.height = "12000"; frame.style.border = "0";
frame.src = "/#";
document.body.append(frame);
const out = (k, v) => { document.documentElement.dataset[k] = v; };
const seen = new Set(); let step = "boot"; let label = null;
const go = (next) => { step = next; out("step", next); };
const tick = setInterval(async () => {
  const doc = frame.contentDocument;
  if (!doc || !doc.body) return;
  const text = doc.body.textContent;
  if (text.includes("Investigating · turn")) seen.add("running");
  if (step === "boot") {
    ENTER
  } else if (step === "picked") {
    go("launched");
    doc.getElementById("investigate").click();
  } else if (step === "launched") {
    if (!frame.contentWindow.location.hash.startsWith("#r/")) return;
    label = decodeURIComponent(frame.contentWindow.location.hash.slice(3));
    out("label", label);
    go("watching");
  } else if (step === "watching") {
    if (!text.includes("Download record")) return;
    go("reading");
    const shown = await (await fetch("/api/runs/" + encodeURIComponent(label))).text();
    out("seen", [...seen].sort().join(","));
    out("fingerprint", doc.querySelector("dd[title]").getAttribute("title"));
    const bytes = new TextEncoder().encode(shown);
    const digest = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
      .map((b) => b.toString(16).padStart(2, "0")).join("");
    out("digest", digest);
    const pre = document.createElement("pre"); pre.id = "text"; pre.textContent = text;
    document.body.append(pre);
    clearInterval(tick);
    go("done");
  }
}, 200);
</script>"""

PICK_THE_SAMPLE = f"""
    const sample = doc.querySelector('[data-incident="{SAMPLE}"]');
    if (!sample) return;
    sample.click();
    go("picked");"""

BRING_A_CSV = """
    const ask = doc.getElementById("composer"), files = doc.getElementById("attach");
    if (!ask || !files) return;
    ask.value = "Revenue fell 45% after yesterday's deploy.";
    ask.dispatchEvent(new Event("input"));
    const dt = new DataTransfer();
    dt.items.add(new File(["day,revenue\\\\n2026-03-07,1200\\\\n2026-03-08,660\\\\n"],
      "revenue.csv", { type: "text/csv" }));
    files.files = dt.files;
    files.dispatchEvent(new Event("change"));
    go("attaching");
  } else if (step === "attaching") {
    if (!doc.body.textContent.includes("revenue.csv")) return;
    go("picked");"""


def drive(tmp_path, monkeypatch, enter: str) -> tuple[dict, str, object]:
    binary = chrome()
    FakeModel.delay = 0.2                    # long enough to be seen running
    model = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=model.serve_forever, daemon=True).start()
    archive = tmp_path / "archive"
    archive.mkdir()
    web = tmp_path / "web"
    shutil.copytree(server.WEB, web)
    (web / "flow.html").write_text(FLOW.replace("ENTER", enter), encoding="utf-8")
    monkeypatch.setattr(server, "ARCHIVE", archive)
    monkeypatch.setattr(server, "WEB", web)
    monkeypatch.setattr(server, "LAUNCH", {
        "provider": "local", "endpoint": f"http://127.0.0.1:{model.server_port}/v1",
        "model": "test-model-1", "served_as": None, "max_turns": 20})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        dom = dump_dom(
            [binary, "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage",
             "--hide-scrollbars", "--no-first-run", f"--user-data-dir={tmp_path / 'chrome'}",
             "--window-size=1480,900", "--virtual-time-budget=36000000", "--dump-dom",
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
    # the record the page drew is the archive's, byte for byte, and said so by its digest
    assert flow["fingerprint"] == flow["digest"]
    text = dom[dom.index('<pre id="text">'):]
    assert "could not be read" not in text
    return flow, text, json.loads((archive / flow["label"] / "record.json").read_text("utf-8"))


def test_a_stranger_picks_a_sample_and_watches_a_fix_it_answer_stand(tmp_path, monkeypatch):
    FakeModel.script[:] = [
        '<TOOL_CALL>{"name": "get_transform", "arguments": {"transform_id": "stg_orders"}}',
        '<TOOL_CALL>{"name": "run_sql", "arguments": {"query": "SELECT distributor, '
        'COUNT(*) FROM raw_orders WHERE order_date = \'2026-08-18\' GROUP BY distributor"}}',
        "<DECISION>" + json.dumps({
            "disposition": "REPAIR", "root_cause_id": "DATA_97",
            "root_cause_summary": "DATA-97 leaves live distributors out of staging.",
            "repair_id": "RESTORE", "patch": {"transforms/stg_orders.sql": STG}})]
    flow, text, record = drive(tmp_path, monkeypatch, PICK_THE_SAMPLE)
    assert flow["label"].startswith(SAMPLE + "-")
    assert "running" in flow["seen"].split(","), flow            # watched, not only the end
    assert record["validation"]["accepted"] and record["authorization"]["authorized"]
    for said in ("Yes. Fix it.", "DATA-97 leaves live distributors out of staging.",
                 "Proposed fix", "Independent rebuild", "Allowed", "Accepted",
                 "Written before the first model request"):
        assert said in text, said
    assert any(e["kind"] == "alert_observed" for e in record["trace"])


def test_a_stranger_brings_their_own_data_and_gets_an_answer(tmp_path, monkeypatch):
    FakeModel.script[:] = [
        '<TOOL_CALL>{"name": "run_sql", "arguments": {"query": "SELECT * FROM revenue"}}',
        '<DECISION>{"disposition": "NO_REPAIR", "root_cause_id": null, "root_cause_summary": '
        '"Two days of revenue, one lower; nothing in the data is malformed.", '
        '"repair_id": null, "patch": {}}']
    flow, text, record = drive(tmp_path, monkeypatch, BRING_A_CSV)
    assert flow["label"].startswith("upload-")
    assert record["context"]["alert"] == "Revenue fell 45% after yesterday's deploy."
    for said in ("No. Leave it.", "Revenue fell 45% after yesterday's deploy.",
                 "Two days of revenue, one lower", "No change proposed"):
        assert said in text, said
