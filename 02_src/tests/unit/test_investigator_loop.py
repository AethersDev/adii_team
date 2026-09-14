import json
from dataclasses import FrozenInstanceError

import pytest
from adii.contracts import IncidentContext, ToolCall, ToolResult
from adii.investigator.loop import STOP_SIGNAL, TOOL_CALL_PREFIX, TurnBudgetExceededError, run
from adii.investigator.provider import ScriptedProvider, ScriptExhaustedError
from adii.investigator.state import InvestigationState

from .fakes import FakeToolExecutor, StateAwareFakeProvider


def incident() -> IncidentContext:
    return IncidentContext(
        incident_id="incident-phase-2",
        alert="A test alert",
        as_of="2026-09-10T00:00:00Z",
    )


def tool_call_response(
    *,
    name: str = "fake_tool",
    arguments: dict[str, object] | None = None,
) -> str:
    intent = {
        "name": name,
        "arguments": {"value": "hello"} if arguments is None else arguments,
    }
    return TOOL_CALL_PREFIX + json.dumps(intent, sort_keys=True)


def test_explicit_stop_emits_one_ordered_event_per_provider_call():
    provider = ScriptedProvider(["first", "second", STOP_SIGNAL])

    trace = run(incident(), provider, FakeToolExecutor(), max_turns=3)

    assert len(trace) == 3
    assert [event.sequence for event in trace] == [0, 1, 2]
    assert [event.kind for event in trace] == ["model_turn", "model_turn", "loop_stopped"]
    assert [event.payload.get("response") for event in trace[:-1]] == ["first", "second"]
    assert trace[-1].payload["reason"] == "explicit_stop"


def test_trace_payloads_carry_incident_id_and_turn_index():
    trace = run(
        incident(),
        ScriptedProvider(["ordinary response", STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=2,
    )

    assert [event.payload["incident_id"] for event in trace] == [
        "incident-phase-2",
        "incident-phase-2",
    ]
    assert [event.payload["turn_index"] for event in trace] == [0, 1]


def test_loop_does_not_call_provider_after_explicit_stop():
    provider = ScriptedProvider([STOP_SIGNAL, "still scripted"])
    executor = FakeToolExecutor()

    trace = run(incident(), provider, executor, max_turns=1)

    assert len(trace) == 1
    assert trace[0].kind == "loop_stopped"
    assert executor.calls == []
    assert provider.received_context == ((),)
    assert provider.respond() == "still scripted"


def test_missing_stop_signal_propagates_script_exhaustion():
    provider = ScriptedProvider(["ordinary response"])

    with pytest.raises(ScriptExhaustedError):
        run(incident(), provider, FakeToolExecutor(), max_turns=2)


def test_budget_allows_normal_completion():
    trace = run(
        incident(),
        ScriptedProvider(["ordinary", STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=4,
    )

    assert [event.kind for event in trace] == ["model_turn", "loop_stopped"]


def test_stop_on_exact_budget_boundary_succeeds():
    trace = run(
        incident(),
        ScriptedProvider(["ordinary", STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=2,
    )

    assert len(trace) == 2
    assert trace[-1].kind == "loop_stopped"


def test_zero_budget_refuses_provider_call_and_attaches_terminal_trace():
    provider = ScriptedProvider([STOP_SIGNAL])

    with pytest.raises(TurnBudgetExceededError) as raised:
        run(incident(), provider, FakeToolExecutor(), max_turns=0)

    assert raised.value.limit == 0
    assert len(raised.value.trace) == 1
    assert raised.value.trace[0].kind == "budget_exceeded"
    assert raised.value.trace[0].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "bound": "max_turns",
        "limit": 0,
    }
    assert provider.respond() == STOP_SIGNAL


def test_negative_budget_is_rejected_before_provider_call():
    provider = ScriptedProvider([STOP_SIGNAL])

    with pytest.raises(ValueError, match="non-negative integer"):
        run(incident(), provider, FakeToolExecutor(), max_turns=-1)

    assert provider.respond() == STOP_SIGNAL


def test_boolean_budgets_are_rejected():
    for invalid in (True, False):
        with pytest.raises(ValueError, match="non-negative integer"):
            run(
                incident(),
                ScriptedProvider([STOP_SIGNAL]),
                FakeToolExecutor(),
                max_turns=invalid,
            )


def test_float_and_nan_budgets_are_rejected():
    for invalid in (1.0, float("nan")):
        with pytest.raises(ValueError, match="non-negative integer"):
            run(
                incident(),
                ScriptedProvider([STOP_SIGNAL]),
                FakeToolExecutor(),
                max_turns=invalid,
            )


def test_explicit_stop_before_budget_exhaustion_succeeds():
    trace = run(
        incident(),
        ScriptedProvider([STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=5,
    )

    assert trace[0].kind == "loop_stopped"


def test_budget_exhaustion_precedes_provider_exhaustion_when_limit_is_smaller():
    provider = ScriptedProvider(["first", "second"])

    with pytest.raises(TurnBudgetExceededError):
        run(incident(), provider, FakeToolExecutor(), max_turns=1)


def test_provider_exhaustion_propagates_when_budget_is_generous():
    provider = ScriptedProvider(["ordinary"])

    with pytest.raises(ScriptExhaustedError):
        run(incident(), provider, FakeToolExecutor(), max_turns=3)


def test_trace_sequence_remains_contiguous_through_budget_event():
    provider = ScriptedProvider(["first", "second"])

    with pytest.raises(TurnBudgetExceededError) as raised:
        run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert [event.sequence for event in raised.value.trace] == [0, 1, 2]
    assert raised.value.trace[-1].kind == "budget_exceeded"


def test_identical_runs_produce_identical_traces():
    script = ["ordinary", STOP_SIGNAL]

    first = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2)
    second = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2)

    assert first == second


def test_n_and_n_minus_one_limits_have_distinct_boundary_results():
    script = ["ordinary", STOP_SIGNAL]

    trace = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2)
    with pytest.raises(TurnBudgetExceededError):
        run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=1)

    assert trace[-1].kind == "loop_stopped"


def test_provider_response_remains_unconsumed_after_budget_refusal():
    provider = ScriptedProvider(["consumed", "still available"])

    with pytest.raises(TurnBudgetExceededError):
        run(incident(), provider, FakeToolExecutor(), max_turns=1)

    assert provider.respond() == "still available"


def test_tool_result_is_delivered_once_then_cleared_after_ordinary_turn():
    provider = ScriptedProvider([tool_call_response(), "after observation", STOP_SIGNAL])
    executor = FakeToolExecutor()

    trace = run(incident(), provider, executor, max_turns=3)

    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "model_turn",
        "loop_stopped",
    ]
    assert [observation is None for observation in provider.received_observations] == [
        True,
        False,
        True,
    ]
    result = executor.results[0]
    assert provider.received_context == ((), (result,), (result,))


def test_tool_call_contract_is_constructed_from_prefixed_json():
    executor = FakeToolExecutor()

    run(
        incident(),
        ScriptedProvider([tool_call_response(arguments={"value": "payload"}), STOP_SIGNAL]),
        executor,
        max_turns=2,
    )

    assert executor.calls == [
        ToolCall(
            call_id="tool-call-0",
            name="fake_tool",
            arguments={"value": "payload"},
        )
    ]


def test_tool_result_is_traced_and_passed_to_provider_by_identity():
    provider = ScriptedProvider([tool_call_response(), STOP_SIGNAL])
    executor = FakeToolExecutor(marker="phase4-handoff-proof")

    trace = run(incident(), provider, executor, max_turns=2)

    result = executor.results[0]
    assert provider.received_observations[1] is result
    assert provider.received_context[1][0] is result
    assert provider.received_observations[1].content["marker"] == "phase4-handoff-proof"
    assert trace[1].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "call_id": "tool-call-0",
        "name": "fake_tool",
        "status": "OK",
        "content": {"value": "hello", "marker": "phase4-handoff-proof"},
    }


def test_provider_receives_none_until_a_tool_result_exists():
    provider = ScriptedProvider(["ordinary", tool_call_response(), STOP_SIGNAL])
    executor = FakeToolExecutor()

    run(incident(), provider, executor, max_turns=3)

    assert provider.received_observations[:2] == (None, None)
    assert provider.received_observations[2] is executor.results[0]


def test_later_tool_result_replaces_cleared_observation_for_one_call():
    provider = ScriptedProvider(
        [
            tool_call_response(arguments={"value": "first"}),
            "after first result",
            tool_call_response(arguments={"value": "second"}),
            "after second result",
            STOP_SIGNAL,
        ]
    )
    executor = FakeToolExecutor()

    run(incident(), provider, executor, max_turns=5)

    assert provider.received_observations == (
        None,
        executor.results[0],
        None,
        executor.results[1],
        None,
    )
    assert provider.received_context == (
        (),
        (executor.results[0],),
        (executor.results[0],),
        (executor.results[0], executor.results[1]),
        (executor.results[0], executor.results[1]),
    )


def test_unknown_tool_denial_is_observed_and_loop_continues():
    provider = ScriptedProvider([tool_call_response(name="unknown"), STOP_SIGNAL])

    trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert trace[1].kind == "tool_result"
    assert trace[1].payload["status"] == "DENIED"
    assert trace[-1].kind == "loop_stopped"
    assert provider.received_observations[1].status == "DENIED"
    assert provider.received_context[1][0].status == "DENIED"


def test_malformed_arguments_are_rejected_and_loop_continues():
    provider = ScriptedProvider(
        [tool_call_response(arguments={"value": 123}), STOP_SIGNAL]
    )

    trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert trace[1].payload["status"] == "REJECTED"
    assert trace[-1].kind == "loop_stopped"
    assert provider.received_observations[1].status == "REJECTED"
    assert provider.received_context[1][0].status == "REJECTED"


def test_controlled_tool_error_is_recorded_and_loop_continues():
    provider = ScriptedProvider(
        [tool_call_response(arguments={"fail": True}), STOP_SIGNAL]
    )

    trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert trace[1].payload["status"] == "ERROR"
    assert trace[-1].kind == "loop_stopped"
    assert provider.received_observations[1].status == "ERROR"
    assert provider.received_context[1][0].status == "ERROR"


def test_tool_trace_order_sequences_and_logical_turn_indexes():
    trace = run(
        incident(),
        ScriptedProvider([tool_call_response(), STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=2,
    )

    assert [event.kind for event in trace] == ["tool_call", "tool_result", "loop_stopped"]
    assert [event.sequence for event in trace] == [0, 1, 2]
    assert [event.payload["turn_index"] for event in trace] == [0, 0, 1]


def test_tool_round_trip_consumes_one_turn_and_budget_blocks_stop():
    provider = ScriptedProvider([tool_call_response(), STOP_SIGNAL])

    with pytest.raises(TurnBudgetExceededError) as raised:
        run(incident(), provider, FakeToolExecutor(), max_turns=1)

    assert [event.kind for event in raised.value.trace] == [
        "tool_call",
        "tool_result",
        "budget_exceeded",
    ]
    assert raised.value.trace[-1].payload["turn_index"] == 1
    assert provider.received_context == ((),)
    assert provider.respond() == STOP_SIGNAL


def test_repeated_tool_runs_are_deterministic():
    script = [tool_call_response(), STOP_SIGNAL]

    first = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2)
    second = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2)

    assert first == second


def test_malformed_tool_call_json_is_rejected_without_executor_dispatch():
    provider = ScriptedProvider([TOOL_CALL_PREFIX + "{not-json", STOP_SIGNAL])
    executor = FakeToolExecutor()

    trace = run(incident(), provider, executor, max_turns=2)

    result = provider.received_observations[1]
    assert executor.calls == []
    assert result is not None
    assert result.call_id == "tool-call-0"
    assert result.status == "REJECTED"
    assert provider.received_context == ((), (result,))
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == [0, 1, 2]
    assert [event.payload["turn_index"] for event in trace] == [0, 0, 1]


@pytest.mark.parametrize(
    "intent",
    [
        [],
        {"arguments": {}},
        {"name": "", "arguments": {}},
        {"name": "   ", "arguments": {}},
        {"name": 123, "arguments": {}},
        {"name": "fake_tool", "arguments": []},
        {"name": "fake_tool", "arguments": None},
    ],
)
def test_structurally_invalid_tool_call_envelopes_are_rejected_without_dispatch(intent):
    provider = ScriptedProvider(
        [TOOL_CALL_PREFIX + json.dumps(intent, sort_keys=True), STOP_SIGNAL]
    )
    executor = FakeToolExecutor()

    trace = run(incident(), provider, executor, max_turns=2)

    assert executor.calls == []
    assert trace[0].kind == "tool_call"
    assert trace[1].kind == "tool_result"
    assert trace[1].payload["call_id"] == "tool-call-0"
    assert trace[1].payload["status"] == "REJECTED"
    assert provider.received_observations[1].status == "REJECTED"
    assert provider.received_context[1][0] is provider.received_observations[1]
    assert trace[-1].kind == "loop_stopped"


def test_absent_arguments_default_to_empty_object_before_executor_dispatch():
    provider = ScriptedProvider(
        [TOOL_CALL_PREFIX + json.dumps({"name": "fake_tool"}), STOP_SIGNAL]
    )
    executor = FakeToolExecutor()

    trace = run(incident(), provider, executor, max_turns=2)

    assert executor.calls == [
        ToolCall(call_id="tool-call-0", name="fake_tool", arguments={})
    ]
    assert trace[1].payload["status"] == "REJECTED"
    assert trace[-1].kind == "loop_stopped"


def test_investigation_state_is_frozen_and_value_based():
    result = ToolResult("call-1", "fake_tool", "OK")
    state = InvestigationState(observations=(result,))

    assert state == InvestigationState(observations=(result,))
    with pytest.raises(FrozenInstanceError):
        state.observations = ()


def test_multiple_tool_results_accumulate_in_order_with_exact_identity():
    provider = ScriptedProvider(
        [
            tool_call_response(arguments={"value": "first"}),
            tool_call_response(arguments={"value": "second"}),
            STOP_SIGNAL,
        ]
    )
    executor = FakeToolExecutor()

    trace = run(incident(), provider, executor, max_turns=3)

    first, second = executor.results
    assert provider.received_observations == (None, first, second)
    assert provider.received_context == ((), (first,), (first, second))
    assert provider.received_context[1][0] is first
    assert provider.received_context[2][0] is first
    assert provider.received_context[2][1] is second
    assert [event.payload["turn_index"] for event in trace] == [0, 0, 1, 1, 2]


def test_accumulated_result_content_causes_different_next_tool_call():
    matched_response = tool_call_response(arguments={"value": "matched-path"})
    unmatched_response = tool_call_response(arguments={"value": "unmatched-path"})
    provider_arguments = {
        "watch_marker": "target",
        "response_if_matched": matched_response,
        "response_if_unmatched": unmatched_response,
    }
    matched_executor = FakeToolExecutor(marker="target")
    unmatched_executor = FakeToolExecutor(marker="something-else")

    run(
        incident(),
        StateAwareFakeProvider(**provider_arguments),
        matched_executor,
        max_turns=3,
    )
    run(
        incident(),
        StateAwareFakeProvider(**provider_arguments),
        unmatched_executor,
        max_turns=3,
    )

    assert matched_executor.calls[0] == unmatched_executor.calls[0]
    assert matched_executor.calls[1].arguments == {"value": "matched-path"}
    assert unmatched_executor.calls[1].arguments == {"value": "unmatched-path"}
