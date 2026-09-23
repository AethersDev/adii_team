"""Task A end-to-end verification through Task B's real controlled-tool boundary."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator

import pytest
from adii.contracts import Disposition, IncidentContext, ToolResult
from adii.investigator.loop import (
    DECISION_PREFIX,
    TOOL_CALL_PREFIX,
    ProviderFailureError,
    TurnBudgetExceededError,
    run,
)
from adii.investigator.provider import ScriptedProvider, ScriptExhaustedError
from adii.tools import ToolExecutor, build_sql_tools, open_walkthrough_world

from ..unit.fakes import END, ENDED

ResponseFactory = Callable[[int, ToolResult | None, tuple[ToolResult, ...]], str]


class _CausalProvider:
    """Build each deterministic response from the context Task A actually supplies."""

    def __init__(self, response_for_turn: ResponseFactory) -> None:
        self._response_for_turn = response_for_turn
        self._turn = 0
        self.received_observations: list[ToolResult | None] = []
        self.received_context: list[tuple[ToolResult, ...]] = []

    def respond(
        self,
        *,
        observation: ToolResult | None = None,
        observations: tuple[ToolResult, ...] = (),
    ) -> str:
        self.received_observations.append(observation)
        self.received_context.append(observations)
        response = self._response_for_turn(self._turn, observation, observations)
        self._turn += 1
        return response


def _incident(incident_id: str, alert: str) -> IncidentContext:
    return IncidentContext(
        incident_id=incident_id,
        alert=alert,
        as_of="2026-09-14T00:00:00Z",
    )


def _tool_call(name: str, arguments: dict[str, object]) -> str:
    return TOOL_CALL_PREFIX + json.dumps(
        {"name": name, "arguments": arguments},
        sort_keys=True,
    )


def _decision(**content: object) -> str:
    return DECISION_PREFIX + json.dumps(content, sort_keys=True)


def _assert_trace(
    trace,
    *,
    incident_id: str,
    kinds: list[str],
    turn_indexes: list[int],
) -> None:
    assert [event.kind for event in trace] == kinds
    assert [event.sequence for event in trace] == list(range(len(trace)))
    assert [event.payload["turn_index"] for event in trace] == turn_indexes
    assert all(event.payload["incident_id"] == incident_id for event in trace)
    for call_index in (
        index for index, event in enumerate(trace) if event.kind == "tool_call"
    ):
        result_index = call_index + 1
        assert trace[result_index].kind == "tool_result"
        assert trace[call_index].payload["call_id"] == trace[result_index].payload[
            "call_id"
        ]


@pytest.fixture
def executor() -> Iterator[ToolExecutor]:
    database = open_walkthrough_world()
    try:
        yield build_sql_tools(database)
    finally:
        database.close()


def test_multi_step_repair_with_causally_derived_second_query(
    executor: ToolExecutor,
):
    incident = _incident(
        "task-a-e2e-repair",
        "mart_daily revenue appears implausibly low",
    )
    derived: dict[str, object] = {}

    def response_for_turn(
        turn: int,
        observation: ToolResult | None,
        observations: tuple[ToolResult, ...],
    ) -> str:
        if turn == 0:
            assert observation is None
            assert observations == ()
            return _tool_call(
                "run_sql",
                {
                    "query": (
                        "SELECT day AS order_date, revenue_usd FROM mart_daily "
                        "ORDER BY day LIMIT 1"
                    )
                },
            )
        if turn == 1:
            assert observation is observations[0]
            order_date, revenue = observation.content["rows"][0]
            derived["order_date"] = order_date
            derived["revenue"] = revenue
            derived["second_query"] = (
                "SELECT order_date, COUNT(*) AS order_count FROM orders "
                f"WHERE order_date = '{order_date}' GROUP BY order_date"
            )
            return _tool_call("run_sql", {"query": derived["second_query"]})
        if turn == 2:
            assert observation is observations[1]
            raw_date, raw_count = observation.content["rows"][0]
            assert raw_date == derived["order_date"]
            derived["raw_count"] = raw_count
            return _decision(
                disposition="REPAIR",
                root_cause_id="double-normalization",
                root_cause_summary=(
                    f"mart_daily reports {derived['revenue']} for {raw_date}, while "
                    f"the raw source contains {raw_count} orders for that date; the "
                    "revenue transformation is applying an extra normalization."
                ),
                repair_id="repair-remove-extra-normalization",
                patch={"stg_orders.sql": "apply cents-to-dollars normalization once"},
            )
        raise AssertionError(f"unexpected provider turn {turn}")

    provider = _CausalProvider(response_for_turn)

    decision, trace = run(incident, provider, executor, max_turns=3)

    first, second = provider.received_context[2]
    assert executor.calls_dispatched == 2
    assert first.status == "OK"
    assert second.status == "OK"
    assert first.content["rows"] == [["2026-01-12", 2.98]]
    assert second.content["rows"] == [["2026-01-12", 298]]
    assert derived["raw_count"] == 298
    assert trace[2].payload["arguments"]["query"] == derived["second_query"]
    assert provider.received_observations == [None, first, second]
    assert provider.received_context == [(), (first,), (first, second)]
    assert provider.received_observations[1] is first
    assert provider.received_observations[2] is second
    assert provider.received_context[1][0] is first
    assert provider.received_context[2][0] is first
    assert provider.received_context[2][1] is second
    assert decision is not None
    assert decision.disposition is Disposition.REPAIR
    assert decision.root_cause_summary
    assert decision.repair_id
    assert decision.patch
    _assert_trace(
        trace,
        incident_id=incident.incident_id,
        kinds=[
            "tool_call",
            "tool_result",
            "tool_call",
            "tool_result",
            "decision_submitted",
        ],
        turn_indexes=[0, 0, 1, 1, 2],
    )
    assert [trace[index].payload["call_id"] for index in (0, 2)] == [
        "tool-call-0",
        "tool-call-1",
    ]


def test_no_repair_from_real_duplicate_check(executor: ToolExecutor):
    incident = _incident(
        "task-a-e2e-no-repair",
        "Orders may have been duplicated",
    )
    duplicate_query = (
        "SELECT order_id, COUNT(*) FROM orders GROUP BY order_id "
        "HAVING COUNT(*) > 1"
    )

    def response_for_turn(
        turn: int,
        observation: ToolResult | None,
        observations: tuple[ToolResult, ...],
    ) -> str:
        if turn == 0:
            return _tool_call("run_sql", {"query": duplicate_query})
        assert turn == 1
        assert observation is observations[0]
        assert observation.content["rows"] == []
        return _decision(
            disposition="NO_REPAIR",
            root_cause_id=None,
            root_cause_summary=(
                "The real duplicate check returned no duplicate order IDs, so no "
                "intervention is justified."
            ),
        )

    provider = _CausalProvider(response_for_turn)

    decision, trace = run(incident, provider, executor, max_turns=2)

    result = provider.received_observations[1]
    assert result is not None
    assert result.status == "OK"
    assert result.content["rows"] == []
    assert provider.received_context == [(), (result,)]
    assert provider.received_context[1][0] is result
    assert decision is not None
    assert decision.disposition is Disposition.NO_REPAIR
    _assert_trace(
        trace,
        incident_id=incident.incident_id,
        kinds=["tool_call", "tool_result", "decision_submitted"],
        turn_indexes=[0, 0, 1],
    )


def test_escalate_from_real_denied_tool_access(executor: ToolExecutor):
    incident = _incident(
        "task-a-e2e-escalate",
        "An authoritative receipt is required",
    )

    def response_for_turn(
        turn: int,
        observation: ToolResult | None,
        observations: tuple[ToolResult, ...],
    ) -> str:
        if turn == 0:
            return _tool_call("get_authoritative_receipt", {"batch_id": "batch-1"})
        assert turn == 1
        assert observation is observations[0]
        assert observation.status == "DENIED"
        return _decision(
            disposition="ESCALATE",
            root_cause_id="missing-authoritative-receipt-access",
            root_cause_summary=(
                "The controlled tool boundary denied access to the unregistered "
                f"authoritative receipt tool: {observation.content['error']}"
            ),
        )

    provider = _CausalProvider(response_for_turn)

    decision, trace = run(incident, provider, executor, max_turns=2)

    result = provider.received_observations[1]
    assert result is not None
    assert result.status == "DENIED"
    assert provider.received_context == [(), (result,)]
    assert provider.received_context[1][0] is result
    assert decision is not None
    assert decision.disposition is Disposition.ESCALATE
    assert "denied access" in decision.root_cause_summary.lower()
    _assert_trace(
        trace,
        incident_id=incident.incident_id,
        kinds=["tool_call", "tool_result", "decision_submitted"],
        turn_indexes=[0, 0, 1],
    )
    assert trace[1].payload["status"] == "DENIED"


def test_provider_exhaustion_after_real_tool_call(executor: ToolExecutor):
    incident = _incident(
        "task-a-e2e-provider-exhaustion",
        "Provider exhausts after observing the warehouse",
    )
    provider = ScriptedProvider(
        [_tool_call("run_sql", {"query": "SELECT COUNT(*) FROM orders"})]
    )

    with pytest.raises(ScriptExhaustedError) as raised:
        run(incident, provider, executor, max_turns=2)

    result = provider.received_observations[1]
    assert not isinstance(raised.value, ProviderFailureError)
    assert raised.value.__cause__ is None
    assert executor.calls_dispatched == 1
    assert result is not None
    assert result.status == "OK"
    assert result.call_id == "tool-call-0"
    assert provider.received_context == ((), (result,))
    assert provider.received_context[1][0] is result


def test_budget_exhaustion_after_real_tool_call(executor: ToolExecutor):
    incident = _incident(
        "task-a-e2e-budget-exhaustion",
        "The turn budget ends after one warehouse observation",
    )
    provider = ScriptedProvider(
        [
            _tool_call("run_sql", {"query": "SELECT COUNT(*) FROM orders"}),
            "must remain unconsumed",
        ]
    )

    with pytest.raises(TurnBudgetExceededError) as raised:
        run(incident, provider, executor, max_turns=1)

    assert executor.calls_dispatched == 1
    assert provider.received_observations == (None,)
    _assert_trace(
        raised.value.trace,
        incident_id=incident.incident_id,
        kinds=["tool_call", "tool_result", "budget_exceeded"],
        turn_indexes=[0, 0, 1],
    )
    assert provider.respond() == "must remain unconsumed"


def test_malformed_envelope_after_real_tool_call_still_recoverable(
    executor: ToolExecutor,
):
    incident = _incident(
        "task-a-e2e-malformed-recovery",
        "Recover after malformed model tool output",
    )
    provider = ScriptedProvider(
        [
            _tool_call("run_sql", {"query": "SELECT COUNT(*) FROM orders"}),
            TOOL_CALL_PREFIX + "{not-json",
            END,
        ]
    )

    decision, trace = run(incident, provider, executor, max_turns=3)

    real_result = provider.received_observations[1]
    rejected_result = provider.received_observations[2]
    assert decision == ENDED
    assert executor.calls_dispatched == 1
    assert real_result is not None
    assert rejected_result is not None
    assert real_result.status == "OK"
    assert rejected_result.status == "REJECTED"
    assert rejected_result.call_id == "tool-call-1"
    assert provider.received_observations == (None, real_result, rejected_result)
    assert provider.received_context == (
        (),
        (real_result,),
        (real_result, rejected_result),
    )
    assert provider.received_context[1][0] is real_result
    assert provider.received_context[2][0] is real_result
    assert provider.received_context[2][1] is rejected_result
    _assert_trace(
        trace,
        incident_id=incident.incident_id,
        kinds=[
            "tool_call",
            "tool_result",
            "tool_call",
            "tool_result",
            "decision_submitted",
        ],
        turn_indexes=[0, 0, 1, 1, 2],
    )
