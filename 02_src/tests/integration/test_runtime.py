"""One command, one incident, one archived run, one report — and the trace is the
harness's, not the investigator's, for every way a run can end."""
from __future__ import annotations

import json
import math
from dataclasses import replace

import pytest
from adii.contracts import (
    Disposition,
    InvestigationDecision,
    ToolCall,
    ToolResult,
    ValidationResult,
)
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
                                    "tools": ["get_schema", "run_sql", "get_transform"],
                                    "max_tool_calls": 30}
    out = capsys.readouterr().out
    assert "ADII INVESTIGATION REPORT" in out and "decided by the validator" in out


def brought(tmp_path, files: dict[str, bytes], world: str = "CREATE TABLE orders (id INTEGER);"):
    """An operator's incident folder: incident.json, world.sql, and `files` by relative path."""
    folder = tmp_path / "brought"
    folder.mkdir()
    (folder / "incident.json").write_text(json.dumps({
        "incident_id": "brought-1", "alert": "orders differ", "as_of": "2026-09-19",
        "permitted_write_paths": []}), encoding="utf-8")
    (folder / "world.sql").write_text(world, encoding="utf-8")
    for relative, content in files.items():
        (folder / relative).parent.mkdir(exist_ok=True)
        (folder / relative).write_bytes(content)
    return folder


def observation(tools, name, arguments):
    result = tools.execute(ToolCall("c", name, arguments))
    assert result.status == "OK", result.content
    return {key: value for key, value in result.content.items() if key != "evidence_id"}


DECLARATION = (b'{\r\n  "source": "vendor.orders_feed",\r\n  "schema_version": 3,\r\n'
               b'  "fields": {"amount": {"type": "number", "unit": "usd", '
               b'"note": "Major units; v3 changed this from cents."}}\r\n}\r\n')
HISTORY = (b"# Transform change history\r\n\r\n"
           b"| date | file | ticket | change |\r\n"
           b"| --- | --- | --- | --- |\r\n"
           b"| 2026-07-08 | `staging/stg_orders.sql` | DATA-412 | Restrict revenue. |\r\n")
BUNDLES = {                       # every evidence kind an incident folder may carry
    "transform_map.json": b'{"stg_orders": "orders.sql"}',
    "transform_sources/orders.sql": b"select id\r\nfrom orders\r\n",
    "notice_map.json": b'{"vendor-change": "vendor.txt"}',
    "notice_sources/vendor.txt": b"Amounts change from cents to dollars on 2026-03-08.\r\n",
    "change_history_map.json": b'{"transform-changes": "CHANGE_HISTORY.md"}',
    "change_history_sources/CHANGE_HISTORY.md": HISTORY,
    "reconciliation_map.json": b'{"upstream-feed": "upstream.log"}',
    "reconciliation_sources/upstream.log": b"first delivery\r\nsecond delivery\r\n",
    "declared_schema_map.json": b'{"orders": "orders.json"}',
    "declared_schema_sources/orders.json": DECLARATION,
}


def test_an_incident_directory_without_evidence_offers_the_sql_surface_only(tmp_path):
    context, tools, world_digest, recorded, evidence = cli.incident_from_dir(brought(tmp_path, {}))
    assert context.incident_id == "brought-1" and recorded is None and evidence == {}
    assert tools.names == ("get_schema", "run_sql")
    assert set(cli.artefacts(context, world_digest, evidence)) == {"incident", "world", "protocol"}


def test_every_evidence_bundle_is_loaded_shown_whole_and_bound_into_the_receipt(tmp_path):
    """Each bundle becomes one tool (or, for a declared schema, a field of `get_schema`), what
    the tool shows is the file's exact text, and the receipt binds each by its digest — the
    source's for what is shown verbatim, and separately the parsed observation's where the
    model sees a parse (the change history, the declared schema)."""
    folder = brought(tmp_path, BUNDLES)
    context, tools, world_digest, _, evidence = cli.incident_from_dir(folder)
    assert tools.names == ("get_schema", "run_sql", "get_transform", "get_notice",
                           "get_change_history", "read_reconciliation")
    transform = observation(tools, "get_transform", {"transform_id": "stg_orders"})
    assert transform["source"] == "select id\r\nfrom orders\r\n" and transform["truncated"] is False
    notice = observation(tools, "get_notice", {"notice_id": "vendor-change"})
    assert notice["content"] == BUNDLES["notice_sources/vendor.txt"].decode("utf-8")
    history = observation(tools, "get_change_history", {"history_id": "transform-changes"})
    assert history["changes"] == [{"date": "2026-07-08", "file": "`staging/stg_orders.sql`",
                                   "ticket": "DATA-412", "change": "Restrict revenue."}]
    window = observation(tools, "read_reconciliation", {"reconciliation_id": "upstream-feed"})
    assert window["lines"] == ["first delivery", "second delivery"]
    schema = observation(tools, "get_schema", {"table": "orders"})
    assert schema["columns"] == ["id"] and schema["declared_schema"] == {
        "source": "vendor.orders_feed", "schema_version": 3,
        "fields": {"amount": {"type": "number", "unit": "usd",
                              "note": "Major units; v3 changed this from cents."}}}
    assert evidence == {
        "transforms": cli.digest_of(cli.canonical_json({"stg_orders": transform["source"]})),
        "notices": cli.digest_of(cli.canonical_json({"vendor-change": notice["content"]})),
        "change_history_source": cli.digest_of(HISTORY.decode("utf-8")),
        "change_history_observation": cli.digest_of(cli.canonical_json(history)),
        "reconciliation_source": cli.digest_of(cli.canonical_json({
            "upstream-feed": BUNDLES["reconciliation_sources/upstream.log"].decode("utf-8")})),
        "declared_schema_source": cli.digest_of(cli.canonical_json({
            "orders": DECLARATION.decode("utf-8")})),
        "declared_schema_observation": cli.digest_of(cli.canonical_json({
            "orders": schema["declared_schema"]})),
    }
    receipt = cli.artefacts(context, world_digest, evidence)
    assert {key: receipt[key] for key in evidence} == evidence
    assert set(receipt) == {"incident", "world", "protocol", *evidence}


def test_one_bundle_alone_adds_only_its_own_tool_and_receipt_names(tmp_path):
    folder = brought(tmp_path, {name: content for name, content in BUNDLES.items()
                                if name.startswith("notice")})
    _, tools, _, _, evidence = cli.incident_from_dir(folder)
    assert tools.names == ("get_schema", "run_sql", "get_notice") and set(evidence) == {"notices"}


def test_keeping_an_incident_copies_every_bundle_byte_for_byte_and_only_regular_files(tmp_path):
    """The run's folder receives the package as it is — the map files, every file under the
    bundle directories — and a symbolic link, which the loaders refuse where it stands, is
    refused here too, before a copy could turn it into a regular file."""
    folder = brought(tmp_path, BUNDLES)
    kept = tmp_path / "kept"
    kept.mkdir()
    cli.keep_incident(folder, kept)
    for relative in ("incident.json", "world.sql", *BUNDLES):
        assert (kept / relative).read_bytes() == (folder / relative).read_bytes(), relative
    assert cli.incident_from_dir(kept)[4] == cli.incident_from_dir(folder)[4]
    outside = tmp_path / "outside.sql"
    outside.write_text("select secret from answer_key", encoding="utf-8")
    (folder / "transform_sources" / "orders.sql").unlink()
    (folder / "transform_sources" / "orders.sql").symlink_to(outside)
    again = tmp_path / "again"
    again.mkdir()
    with pytest.raises(ValueError, match="must be a regular file"):
        cli.keep_incident(folder, again)


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


def test_a_validator_that_returns_the_legacy_placeholder_is_our_defect(capsys):
    """Row 3: the runtime records a verdict or NOT_CHECKABLE, nothing else. A validator that
    answers with the shape of records before 22 September — not accepted, no checks, no
    reason — has not said whether it checked anything; that is our defect, archived as an
    infrastructure failure, never a record that reads as nobody having looked."""
    context, recorded = load()
    investigator, tools, _ = replay(recorded)
    legacy = ScriptedValidator(ValidationResult(accepted=False, report="no validator yet"))
    run = harness(context, investigator, tools, legacy)
    assert run.termination == "infrastructure_failure" and run.validation is None
    assert "legacy unchecked result" in run.detail
    assert run.trace[-1].kind == "decision_submitted"      # nothing recorded past the defect
    assert "legacy unchecked result" in capsys.readouterr().err


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
