"""The per-layer counts registered with the local extension pack. The corrective refusals are
the real loop's, through the grid and the scripted stand-in endpoint; the terminal ones are
read from a record's two facts. No count here is typed by hand."""
from __future__ import annotations

import importlib.util
import json
import threading
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from adii.contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    RepairAuthorization,
    ValidationResult,
)
from adii.evaluation import grid
from adii.investigator.loop import DECISION_PREFIX, TOOL_CALL_PREFIX
from adii.reporting.record import RunRecord, write_record

from ..unit.fakes import END
from .fake_model import FakeModel

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "layer_counts.py"
spec = importlib.util.spec_from_file_location("layer_counts", SCRIPT)
counts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(counts)
INCIDENT = grid.PARTITION["benchmark"][0]


@pytest.fixture
def endpoint():
    FakeModel.script, FakeModel.seen, FakeModel.usage = [], [], None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()
    httpd.server_close()


def test_a_corrective_refusal_is_counted_under_the_check_that_fired(tmp_path, endpoint):
    schema = json.dumps({"name": "get_schema", "arguments": {}})
    FakeModel.script[:] = [
        TOOL_CALL_PREFIX + schema + " and then some text",   # protocol: refused, told why
        TOOL_CALL_PREFIX + schema,                            # an observation
        DECISION_PREFIX + json.dumps({"disposition": "NO_REPAIR", "root_cause_id": None,
                                      "root_cause_summary": "Nothing is wrong.",
                                      "evidence_refs": ["ev-never-minted"]}),   # evidence
        END,                                                  # the first run ends
        END]                                                  # the second is unaided
    archive, packs = tmp_path / "runs", tmp_path / "packs"
    assert grid.main(["--pack", "t", "--provider", "local", "--model", "m", "--endpoint",
                      endpoint, "--incidents", INCIDENT, "--arms", "full", "--repeats", "2",
                      "--archive", str(archive), "--packs", str(packs)]) == 0
    text = counts.summary(json.loads((packs / "t.json").read_text(encoding="utf-8")), archive)
    assert "| protocol | corrective | 1 | 1/2 |" in text
    assert "| evidence | corrective | 1 | 1/2 |" in text
    assert "| entitlement | terminal | 0 | 0/2 |" in text
    assert "Unaided runs: 1/2." in text
    assert "Fixes proposed: 0; refused by a terminal check: 0; admitted: 0." in text
    assert f"`t-{INCIDENT}-full-r1` (evidence 1, protocol 1)" in text


def test_a_terminal_refusal_is_read_from_the_runs_two_facts(tmp_path):
    target = "marts/mart_daily_revenue.sql"
    record = RunRecord(
        label="t-x-full-r1", context=IncidentContext("x", "An alert.", "2026-09-30T00:00:00Z"),
        trace=(), termination="submitted", detail="submitted",
        decision=InvestigationDecision(Disposition.REPAIR, "cause", "A fix.",
                                       repair_id="fix", patch={target: "SELECT 1"}),
        validation=ValidationResult(accepted=False, report="Rejected.", checks_run=("rebuild",)),
        tool_calls=0, model_turns=1, api_cost_usd=0.0, latency_ms=0, configuration={},
        provenance={}, authorization=RepairAuthorization(
            authorized=False, checked_paths=(target,), denied_paths=(target,),
            reason_code="target_not_permitted"))
    assert counts.fired(record) == {"entitlement": 1, "validity": 1}
    write_record(record, tmp_path)
    pack = {"pack": "t", "incidents": ["x"], "arms": ["full"], "repeats": 1}
    assert "Fixes proposed: 1; refused by a terminal check: 1; admitted: 0." in \
        counts.summary(pack, tmp_path)
    # a verdict nobody could establish is not a rejection, and is not counted as one
    unchecked = ValidationResult(accepted=False, report="Not checkable.",
                                 reason_code="no_rebuildable_world")
    assert counts.fired(replace(record, validation=unchecked)) == {"entitlement": 1}
