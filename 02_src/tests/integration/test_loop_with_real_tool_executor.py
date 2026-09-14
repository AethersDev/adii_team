"""Task A loop integration with Task B's real controlled-tool executor."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from adii.contracts import IncidentContext
from adii.investigator.loop import STOP_SIGNAL, TOOL_CALL_PREFIX, run
from adii.investigator.provider import ScriptedProvider
from adii.tools import ToolExecutor, build_sql_tools, open_walkthrough_world


def incident() -> IncidentContext:
    return IncidentContext(
        incident_id="incident-phase-6",
        alert="Verify the real controlled-tool boundary",
        as_of="2026-09-14T00:00:00Z",
    )


def tool_call(name: str, arguments: dict[str, object]) -> str:
    return TOOL_CALL_PREFIX + json.dumps(
        {"name": name, "arguments": arguments},
        sort_keys=True,
    )


@pytest.fixture
def executor() -> Iterator[ToolExecutor]:
    database = open_walkthrough_world()
    try:
        yield build_sql_tools(database)
    finally:
        database.close()


def test_investigator_traces_real_ok_result_with_evidence(executor: ToolExecutor):
    provider = ScriptedProvider(
        [
            tool_call(
                "run_sql",
                {"query": "SELECT COUNT(*) AS order_count FROM orders"},
            ),
            STOP_SIGNAL,
        ]
    )

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
    result = provider.received_observations[1]
    assert result is not None
    assert result.status == "OK"
    assert result.call_id == "tool-call-0"
    assert result.content["evidence_id"].startswith("ev-")
    assert result.content["rows"] == [[896]]
    assert provider.received_observations == (None, result)
    assert provider.received_context == ((), (result,))
    assert provider.received_context[1][0] is result
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == [0, 1, 2]
    assert [event.payload["turn_index"] for event in trace] == [0, 0, 1]
    assert trace[0].payload["call_id"] == "tool-call-0"
    assert trace[1].payload["status"] == "OK"
    assert trace[1].payload["content"] is result.content


def test_investigator_observes_real_denial_once_and_continues(
    executor: ToolExecutor,
):
    provider = ScriptedProvider(
        [
            tool_call("delete_table", {"table": "orders"}),
            "continue after denial",
            STOP_SIGNAL,
        ]
    )

    decision, trace = run(incident(), provider, executor, max_turns=3)

    assert decision is None
    result = provider.received_observations[1]
    assert result is not None
    assert result.status == "DENIED"
    assert result.call_id == "tool-call-0"
    assert provider.received_observations == (None, result, None)
    assert provider.received_context == ((), (result,), (result,))
    assert provider.received_context[1][0] is result
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "model_turn",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == [0, 1, 2, 3]
    assert [event.payload["turn_index"] for event in trace] == [0, 0, 1, 2]
    assert trace[1].payload["status"] == "DENIED"


def test_investigator_accumulates_real_rejection_and_preserves_prior_result(
    executor: ToolExecutor,
):
    provider = ScriptedProvider(
        [
            tool_call("run_sql", {"query": "SELECT COUNT(*) FROM orders"}),
            tool_call("run_sql", {"query": 123}),
            "continue after rejection",
            STOP_SIGNAL,
        ]
    )

    decision, trace = run(incident(), provider, executor, max_turns=4)

    assert decision is None
    first = provider.received_observations[1]
    second = provider.received_observations[2]
    assert first is not None
    assert second is not None
    assert first.status == "OK"
    assert second.status == "REJECTED"
    assert first.call_id == "tool-call-0"
    assert second.call_id == "tool-call-1"
    assert provider.received_observations == (None, first, second, None)
    assert provider.received_context == (
        (),
        (first,),
        (first, second),
        (first, second),
    )
    assert provider.received_context[1][0] is first
    assert provider.received_context[2][0] is first
    assert provider.received_context[2][1] is second
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "tool_call",
        "tool_result",
        "model_turn",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == list(range(6))
    assert [event.payload["turn_index"] for event in trace] == [0, 0, 1, 1, 2, 3]
    assert [trace[index].payload["status"] for index in (1, 3)] == [
        "OK",
        "REJECTED",
    ]
