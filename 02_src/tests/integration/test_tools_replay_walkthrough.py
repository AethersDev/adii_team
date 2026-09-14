"""The walkthrough fixture was recorded against a world that did not exist in this
repository. Now it does: every tool call in `01_data/walkthrough/trace.jsonl`, sent
through the real executor against the real read-only database, must come back with the
status and observation the fixture recorded — including the refused one."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from adii.contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    InvestigationRun,
    ToolCall,
    TraceEvent,
)
from adii.reporting import RunRecord, render_run
from adii.tools import GET_SCHEMA, RUN_SQL, build_sql_tools, open_walkthrough_world

FIXTURE = Path(__file__).resolve().parents[3] / "01_data" / "walkthrough"


def fixture_calls() -> list[tuple[dict, dict]]:
    events = [json.loads(line) for line in
              (FIXTURE / "trace.jsonl").read_text(encoding="utf-8").splitlines() if line]
    calls = {e["payload"]["call_id"]: e["payload"] for e in events if e["kind"] == "tool_call"}
    results = {e["payload"]["call_id"]: e["payload"] for e in events if e["kind"] == "tool_result"}
    return [(calls[cid], results[cid]) for cid in calls]


@pytest.fixture
def executor():
    return build_sql_tools(open_walkthrough_world())


def test_the_tool_surface_is_the_first_build_the_readme_asks_for(executor):
    assert executor.names == ("get_schema", "run_sql")
    assert [s["name"] for s in executor.advertised()] == [GET_SCHEMA.name, RUN_SQL.name]


@pytest.mark.parametrize("recorded_call, recorded_result", fixture_calls(),
                         ids=[c["call_id"] for c, _ in fixture_calls()])
def test_every_recorded_call_replays_with_the_recorded_status(
        executor, recorded_call, recorded_result):
    live = executor.execute(ToolCall(call_id=recorded_call["call_id"],
                                     name=recorded_call["name"],
                                     arguments=recorded_call["arguments"]))
    assert live.status == recorded_result["status"]
    assert live.name == recorded_call["name"]
    if live.status == "OK":
        assert live.content["evidence_id"].startswith("ev-")


def test_the_schema_the_fixture_shows_is_the_schema_the_world_has(executor):
    live = executor.execute(ToolCall(call_id="c1", name="get_schema",
                                     arguments={"table": "orders"}))
    assert live.content["columns"] == ["order_id", "order_date", "amount_cents"]


def test_the_source_counts_the_fixture_shows_are_what_the_world_returns(executor):
    query = "SELECT order_date, COUNT(*) AS n FROM orders GROUP BY order_date"
    live = executor.execute(ToolCall(call_id="c2", name="run_sql", arguments={"query": query}))
    assert dict(live.content["rows"]) == {"2026-01-12": 298, "2026-01-13": 301,
                                          "2026-01-14": 297}


def test_the_mart_shows_the_hundredfold_gap_the_incident_is_about(executor):
    live = executor.execute(ToolCall(call_id="c3", name="run_sql", arguments={
        "query": "SELECT * FROM mart_daily WHERE day = '2026-01-14'"}))
    assert live.content["rows"] == [["2026-01-14", 2.97]]


def test_the_refused_call_is_denied_and_never_reaches_the_database(executor):
    live = executor.execute(ToolCall(call_id="c4", name="delete_table",
                                     arguments={"table": "orders"}))
    assert live.status == "DENIED"
    still_there = executor.execute(ToolCall(call_id="c5", name="run_sql", arguments={
        "query": "SELECT count(*) FROM orders"}))
    assert still_there.content["rows"] == [[896]]


def test_live_results_render_through_the_reporting_layer_unchanged(executor):
    """Integration: what the tools return is what telemetry can show. No adapter."""
    trace, sequence = [], 0
    for recorded_call, _ in fixture_calls():
        call = ToolCall(call_id=recorded_call["call_id"], name=recorded_call["name"],
                        arguments=recorded_call["arguments"])
        result = executor.execute(call)
        trace.append(TraceEvent(sequence, "tool_call", {
            "call_id": call.call_id, "name": call.name, "arguments": call.arguments}))
        trace.append(TraceEvent(sequence + 1, "tool_result", {
            "call_id": result.call_id, "name": result.name, "status": result.status,
            "content": result.content}))
        sequence += 2
    context = IncidentContext(incident_id="demo-learning-001", alert="3 where 300 expected",
                              as_of="2026-01-15T00:00:00Z")
    run = InvestigationRun(
        incident_id=context.incident_id, trace=tuple(trace),
        decision=InvestigationDecision(Disposition.NO_REPAIR, None, "rendering test only"),
        tool_calls=sum(1 for e in trace if e.kind == "tool_result"
                       and e.payload["status"] == "OK"))
    report = render_run(RunRecord.from_run("live", context, run, configuration={},
                                           origin="test"))
    assert "<-   [OK] orders: order_id, order_date, amount_cents" in report
    assert "[DENIED] unknown tool 'delete_table'" in report
    assert "tool calls 3" in report
