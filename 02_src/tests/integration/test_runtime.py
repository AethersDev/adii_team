"""One command, one incident, one archived run, one report — and the trace is the
harness's, not the investigator's."""
from __future__ import annotations

from dataclasses import replace

import pytest
from adii.contracts import Disposition, InvestigationDecision, ToolCall, ToolResult
from adii.examples.walkthrough import load
from adii.reporting import read_record
from adii.runtime.__main__ import main
from adii.runtime.fakes import ScriptedInvestigator, ScriptedTools, ScriptedValidator, scripted
from adii.runtime.run import run_incident


def test_one_command_takes_an_incident_to_an_archived_run_and_a_report(tmp_path, capsys):
    code = main(["--incident", "demo-learning-001", "--provider", "fake",
                 "--archive", str(tmp_path), "--label", "first"])
    assert code == 0
    record = read_record(tmp_path / "first" / "record.json")
    assert record.termination == "submitted" and record.provenance["origin"] == "runtime"
    assert record.configuration == {"provider": "fake", "model": None}
    out = capsys.readouterr().out
    assert "ADII INVESTIGATION REPORT" in out and "decided by the validator" in out


def test_the_runtime_reproduces_the_walkthrough_from_scripted_components():
    """The walkthrough's trace was assembled by hand. Driving scripted components through
    the real runtime must produce the same trace, decision and verdict — recorded, not
    declared."""
    context, recorded = load()
    run = run_incident(context, *scripted(recorded))
    assert run.trace == recorded.trace
    assert run.decision == recorded.decision and run.validation == recorded.validation
    assert run.tool_calls == recorded.tool_calls == 3      # the DENIED call is not executed
    assert run.model_turns == 0 and run.api_cost_usd == 0.0


def test_counters_come_from_the_trace_not_from_the_investigator():
    context, recorded = load()
    investigator, tools, validator = scripted(recorded)
    extra = ToolCall(call_id="c9", name="run_sql", arguments={"query": "SELECT 1"})
    tools = ScriptedTools({**tools._results, "c9": ToolResult(
        call_id="c9", name="run_sql", status="OK", content={"rows": [[1]]})})
    investigator = ScriptedInvestigator(investigator._calls + (extra,), investigator._decision)
    run = run_incident(context, investigator, tools, validator)
    assert run.tool_calls == 4
    assert [e.payload["call_id"] for e in run.trace if e.kind == "tool_call"][-1] == "c9"


def test_a_call_the_script_cannot_answer_is_a_harness_error_not_a_refusal():
    context, recorded = load()
    _, tools, _ = scripted(recorded)
    with pytest.raises(ValueError, match="no result for call 'zz'"):
        tools.execute(ToolCall(call_id="zz", name="run_sql"))


def test_only_a_repair_reaches_the_validator():
    context, recorded = load()
    no_repair = InvestigationDecision(disposition=Disposition.NO_REPAIR, root_cause_id=None,
                                      root_cause_summary="the source moved; the mart followed")
    investigator = ScriptedInvestigator((), no_repair)
    run = run_incident(context, investigator, ScriptedTools({}), ScriptedValidator(None))
    assert run.validation is None
    assert [e.kind for e in run.trace] == ["incident_received", "decision_submitted"]
    with pytest.raises(ValueError, match="proposed no repair"):
        ScriptedValidator(None).validate(context, replace(no_repair))


def test_an_unknown_incident_a_bad_label_and_a_taken_label_are_refused(tmp_path, capsys):
    assert main(["--incident", "nope", "--provider", "fake", "--archive", str(tmp_path)]) == 2
    assert "no such incident 'nope'" in capsys.readouterr().out
    escape = ["--incident", "demo-learning-001", "--provider", "fake",
              "--archive", str(tmp_path / "archive"), "--label", "../escape"]
    assert main(escape) == 2
    assert "one path segment" in capsys.readouterr().out
    assert not (tmp_path / "escape").exists()
    args = ["--incident", "demo-learning-001", "--provider", "fake",
            "--archive", str(tmp_path), "--label", "twice", "--no-report"]
    assert main(args) == 0
    assert main(args) == 1
    assert "a label names one run" in capsys.readouterr().out
