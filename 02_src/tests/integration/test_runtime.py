"""One command, one incident, one archived run, one report — and the trace is the
harness's, not the investigator's, for every way a run can end."""
from __future__ import annotations

import math
from dataclasses import replace

import pytest
from adii.contracts import Disposition, InvestigationDecision, ToolCall, ToolResult
from adii.examples.walkthrough import load
from adii.reporting import read_record, write_record
from adii.runtime import __main__ as cli
from adii.runtime.run import Terminated, run_incident
from adii.runtime.scripted import (
    EndingInvestigator,
    ScriptedInvestigator,
    ScriptedTools,
    ScriptedValidator,
    replay,
)
from adii.tools import build_sql_tools, open_walkthrough_world

SCRIPTED = ["--incident", "demo-learning-001", "--provider", "scripted"]


def harness(context, investigator, tools, validator):
    return run_incident("t", context, investigator, tools, validator, configuration={})


def statuses(trace) -> dict[str, str]:
    return {e.payload["call_id"]: e.payload["status"] for e in trace if e.kind == "tool_result"}


def test_one_command_takes_an_incident_to_an_archived_run_and_a_report(tmp_path, capsys):
    assert cli.main([*SCRIPTED, "--archive", str(tmp_path), "--label", "first"]) == 0
    record = read_record(tmp_path / "first" / "record.json")
    assert record.termination == "submitted" and record.provenance["origin"] == "runtime"
    assert record.configuration == {"provider": "scripted", "model": None,
                                    "tools": ["get_schema", "run_sql"]}
    out = capsys.readouterr().out
    assert "ADII INVESTIGATION REPORT" in out and "decided by the validator" in out


def test_the_fake_provider_drives_the_real_tool_layer(tmp_path):
    """The investigator and the validator are scripted; the tools are the real executor over
    the walkthrough world. Every call comes back with the status the fixture recorded, the
    refusal included, and the record carries what the tools actually said — evidence ids
    and all. Only the statuses, the decision and the verdict are the fixture's."""
    assert cli.main([*SCRIPTED, "--archive", str(tmp_path), "--label", "live", "--no-report"]) == 0
    record = read_record(tmp_path / "live" / "record.json")
    _, recorded = load()
    assert statuses(record.trace) == statuses(recorded.trace)
    results = [e.payload for e in record.trace if e.kind == "tool_result"]
    assert all(r["content"]["evidence_id"].startswith("ev-") for r in results
               if r["status"] == "OK")
    assert [r["name"] for r in results if r["status"] == "DENIED"] == ["delete_table"]
    assert record.tool_calls == 3
    assert record.decision == recorded.decision and record.validation == recorded.validation


def test_the_runtime_reproduces_the_walkthrough_from_scripted_components():
    """The walkthrough's trace was assembled by hand. Driving scripted components through
    the real runtime must produce the same trace, decision and verdict — recorded, not
    declared."""
    context, recorded = load()
    run = harness(context, *replay(recorded))
    assert run.trace == recorded.trace
    assert run.decision == recorded.decision and run.validation == recorded.validation
    assert run.tool_calls == recorded.tool_calls == 3      # the DENIED call is not executed
    assert run.model_turns == 0 and run.api_cost_usd == 0.0


def test_counters_come_from_the_trace_not_from_the_investigator():
    context, recorded = load()
    investigator, tools, validator = replay(recorded)
    extra = ToolCall(call_id="c9", name="run_sql", arguments={"query": "SELECT 1"})
    tools = ScriptedTools({**tools._results, "c9": ToolResult(
        call_id="c9", name="run_sql", status="OK", content={"rows": [[1]]})})
    investigator = ScriptedInvestigator(investigator._calls + (extra,), investigator._decision)
    run = harness(context, investigator, tools, validator)
    assert run.tool_calls == 4
    assert [e.payload["call_id"] for e in run.trace if e.kind == "tool_call"][-1] == "c9"


def test_a_call_the_script_cannot_answer_is_a_harness_error_not_a_refusal():
    context, recorded = load()
    _, tools, _ = replay(recorded)
    with pytest.raises(ValueError, match="no result for call 'zz'"):
        tools.execute(ToolCall(call_id="zz", name="run_sql"))


def test_only_a_repair_reaches_the_validator():
    context, recorded = load()
    no_repair = InvestigationDecision(disposition=Disposition.NO_REPAIR, root_cause_id=None,
                                      root_cause_summary="the source moved; the mart followed")
    run = harness(context, ScriptedInvestigator((), no_repair), ScriptedTools({}),
                  ScriptedValidator(None))
    assert run.validation is None
    assert [e.kind for e in run.trace] == ["incident_received", "decision_submitted"]
    with pytest.raises(ValueError, match="proposed no repair"):
        ScriptedValidator(None).validate(context, replace(no_repair))


def test_a_run_the_loop_ends_is_archived_with_the_trace_so_far():
    """The loop's classification travels verbatim; the runtime adds no interpretation."""
    context, recorded = load()
    calls = [ToolCall(e.payload["call_id"], e.payload["name"], e.payload["arguments"])
             for e in recorded.trace if e.kind == "tool_call"][:2]
    bound = Terminated("bound_hit", "tool_calls: 2 of 2 used")
    ended = harness(context, EndingInvestigator(calls, bound),
                    build_sql_tools(open_walkthrough_world()), ScriptedValidator(None))
    assert (ended.termination, ended.detail) == ("bound_hit", "tool_calls: 2 of 2 used")
    assert ended.decision is None and ended.validation is None
    assert [e.kind for e in ended.trace] == ["incident_received", "tool_call", "tool_result",
                                             "tool_call", "tool_result"]
    assert ended.tool_calls == 2
    with pytest.raises(ValueError, match="termination must be one of"):
        Terminated("gave_up", "not a classification the loop may make")


def test_a_defect_of_ours_is_an_archived_infrastructure_failure_not_a_lost_run(capsys):
    context, _ = load()
    call = ToolCall("c1", "get_schema", {"table": "orders"})
    failed = harness(context, EndingInvestigator([call], RuntimeError("the harness tripped")),
                     build_sql_tools(open_walkthrough_world()), ScriptedValidator(None))
    assert failed.termination == "infrastructure_failure"
    assert failed.detail == "RuntimeError: the harness tripped"
    assert [e.kind for e in failed.trace] == ["incident_received", "tool_call", "tool_result"]
    assert "RuntimeError: the harness tripped" in capsys.readouterr().err   # not hidden


def test_a_poisoned_payload_is_archived_as_an_infrastructure_failure(tmp_path):
    """NaN in a tool's answer is our defect, not the model's. The record still lands: every
    event that is strict JSON on its own, and a detail naming the poison."""
    context, _ = load()
    poison = ScriptedTools({"c1": ToolResult("c1", "run_sql", "OK", {"rows": [[math.nan]]})})
    decision = InvestigationDecision(Disposition.NO_REPAIR, None, "nothing to fix")
    record = harness(context, ScriptedInvestigator(
        (ToolCall("c1", "run_sql", {"query": "SELECT 1"}),), decision), poison,
        ScriptedValidator(None))
    assert record.termination == "infrastructure_failure"
    assert "not strict JSON" in record.detail
    assert [e.kind for e in record.trace] == ["incident_received", "tool_call",
                                              "decision_submitted"]
    assert write_record(record, tmp_path).is_file()


def test_the_label_is_claimed_only_after_every_precondition(tmp_path, capsys):
    archive = tmp_path / "archive"
    assert cli.main(["--incident", "nope", "--provider", "scripted",
                     "--archive", str(archive), "--label", "free"]) == 2
    assert "no such incident 'nope'" in capsys.readouterr().out
    assert cli.main([*SCRIPTED, "--archive", str(archive), "--label", "../escape"]) == 2
    assert "one path segment" in capsys.readouterr().out
    assert not archive.exists() and not (tmp_path / "escape").exists()   # both labels reusable
    held = [*SCRIPTED, "--archive", str(archive), "--label", "held", "--no-report"]
    assert cli.main(held) == 0
    first = (archive / "held" / "record.json").read_bytes()
    assert cli.main(held) == 1
    assert "a label names one run" in capsys.readouterr().out
    assert (archive / "held" / "record.json").read_bytes() == first


def test_each_way_a_run_ends_has_its_own_exit_code_and_its_record(tmp_path, capsys,
                                                                   monkeypatch):
    ended = Terminated("model_failure", "the provider returned no content")
    monkeypatch.setattr(cli, "replay",
                        lambda run: (EndingInvestigator((), ended), None, ScriptedValidator(None)))
    assert cli.main([*SCRIPTED, "--archive", str(tmp_path), "--label", "ended"]) == 3
    assert "model_failure: the provider returned no content" in capsys.readouterr().out
    assert read_record(tmp_path / "ended" / "record.json").termination == "model_failure"
    monkeypatch.setattr(cli, "replay",
                        lambda run: (EndingInvestigator((), KeyError("boom")), None,
                                     ScriptedValidator(None)))
    assert cli.main([*SCRIPTED, "--archive", str(tmp_path), "--label", "broke"]) == 4
    broke = read_record(tmp_path / "broke" / "record.json")
    assert broke.termination == "infrastructure_failure" and broke.detail == "KeyError: 'boom'"
