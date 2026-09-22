"""The walkthrough is the team's shared mental model, so it is also a regression test:
if the contracts or the renderer drift, this fails before anyone is confused by it."""
from __future__ import annotations

from pathlib import Path

from adii.contracts import Disposition
from adii.examples.walkthrough import load, main, stages
from adii.reporting import read_record, render_run

WALKTHROUGH = Path(__file__).resolve().parents[3] / "01_data" / "walkthrough"


def test_the_fixture_loads_into_real_contract_objects():
    context, run = load()
    assert context.incident_id == "demo-learning-001"
    assert run.decision.disposition is Disposition.REPAIR
    minted = [e.payload["content"]["evidence_id"] for e in run.trace
              if e.kind == "tool_result" and e.payload["status"] == "OK"]
    assert list(run.decision.evidence_refs) == minted      # it cites what it observed
    assert run.validation.accepted is True
    assert run.tool_calls == 3                       # counted from the trace, not declared


def test_the_denied_tool_call_is_part_of_the_lesson():
    """The tool layer is a boundary, not a helper. The fixture teaches that by showing a
    refusal."""
    _, run = load()
    denied = [e for e in run.trace
              if e.kind == "tool_result" and e.payload["status"] == "DENIED"]
    assert len(denied) == 1 and denied[0].payload["name"] == "delete_table"


def test_the_walk_covers_every_boundary():
    context, run = load()
    narrated = "\n".join(boundary for _, boundary in stages(context, run))
    for boundary in ("IncidentContext", "ToolCall", "ToolResult",
                     "InvestigationDecision", "ValidationResult", "TraceEvent"):
        assert boundary in narrated


def test_the_rendered_report_matches_the_committed_one():
    record = read_record(WALKTHROUGH / "record.json")
    expected = (WALKTHROUGH / "expected_report.txt").read_text(encoding="utf-8")
    assert render_run(record) == expected


def test_it_runs_as_a_module(capsys):
    assert main([]) == 0
    out = capsys.readouterr().out
    assert "ADII INVESTIGATION REPORT" in out
    assert "decided by the validator, never by the agent" in out


def test_archive_writes_the_run_once(tmp_path, capsys):
    """One command, one record, and a label names one run forever."""
    assert main(["--archive", str(tmp_path)]) == 0
    record = read_record(tmp_path / "demo-learning-001" / "record.json")
    assert record.termination == "submitted" and record.tool_calls == 3
    assert main(["--archive", str(tmp_path)]) == 1
    assert "a label names one run" in capsys.readouterr().out
