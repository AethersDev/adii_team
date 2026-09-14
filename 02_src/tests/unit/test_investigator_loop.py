import json
from dataclasses import FrozenInstanceError

import pytest
from adii.contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    ToolCall,
    ToolResult,
)
from adii.investigator.loop import (
    DECISION_PREFIX,
    STOP_SIGNAL,
    TOOL_CALL_PREFIX,
    TurnBudgetExceededError,
    run,
)
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


def decision_response(**overrides: object) -> str:
    submission: dict[str, object] = {
        "disposition": "NO_REPAIR",
        "root_cause_id": "cause-1",
        "root_cause_summary": "The observed condition is legitimate.",
    }
    submission.update(overrides)
    return DECISION_PREFIX + json.dumps(submission, sort_keys=True)


def test_explicit_stop_emits_one_ordered_event_per_provider_call():
    provider = ScriptedProvider(["first", "second", STOP_SIGNAL])

    decision, trace = run(incident(), provider, FakeToolExecutor(), max_turns=3)

    assert decision is None
    assert len(trace) == 3
    assert [event.sequence for event in trace] == [0, 1, 2]
    assert [event.kind for event in trace] == ["model_turn", "model_turn", "loop_stopped"]
    assert [event.payload.get("response") for event in trace[:-1]] == ["first", "second"]
    assert trace[-1].payload["reason"] == "explicit_stop"


def test_trace_payloads_carry_incident_id_and_turn_index():
    decision, trace = run(
        incident(),
        ScriptedProvider(["ordinary response", STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=2,
    )

    assert decision is None
    assert [event.payload["incident_id"] for event in trace] == [
        "incident-phase-2",
        "incident-phase-2",
    ]
    assert [event.payload["turn_index"] for event in trace] == [0, 1]


def test_loop_does_not_call_provider_after_explicit_stop():
    provider = ScriptedProvider([STOP_SIGNAL, "still scripted"])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=1)

    assert decision is None
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
    decision, trace = run(
        incident(),
        ScriptedProvider(["ordinary", STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=4,
    )

    assert decision is None
    assert [event.kind for event in trace] == ["model_turn", "loop_stopped"]


def test_stop_on_exact_budget_boundary_succeeds():
    decision, trace = run(
        incident(),
        ScriptedProvider(["ordinary", STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=2,
    )

    assert decision is None
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
    decision, trace = run(
        incident(),
        ScriptedProvider([STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=5,
    )

    assert decision is None
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

    first_decision, first = run(
        incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2
    )
    second_decision, second = run(
        incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2
    )

    assert first_decision is None
    assert second_decision is None
    assert first == second


def test_n_and_n_minus_one_limits_have_distinct_boundary_results():
    script = ["ordinary", STOP_SIGNAL]

    decision, trace = run(
        incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2
    )
    with pytest.raises(TurnBudgetExceededError):
        run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=1)

    assert decision is None
    assert trace[-1].kind == "loop_stopped"


def test_provider_response_remains_unconsumed_after_budget_refusal():
    provider = ScriptedProvider(["consumed", "still available"])

    with pytest.raises(TurnBudgetExceededError):
        run(incident(), provider, FakeToolExecutor(), max_turns=1)

    assert provider.respond() == "still available"


def test_tool_result_is_delivered_once_then_cleared_after_ordinary_turn():
    provider = ScriptedProvider([tool_call_response(), "after observation", STOP_SIGNAL])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=3)

    assert decision is None
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

    decision, _ = run(
        incident(),
        ScriptedProvider([tool_call_response(arguments={"value": "payload"}), STOP_SIGNAL]),
        executor,
        max_turns=2,
    )

    assert decision is None
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

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
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

    decision, _ = run(incident(), provider, executor, max_turns=3)

    assert decision is None
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

    decision, _ = run(incident(), provider, executor, max_turns=5)

    assert decision is None
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

    decision, trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert decision is None
    assert trace[1].kind == "tool_result"
    assert trace[1].payload["status"] == "DENIED"
    assert trace[-1].kind == "loop_stopped"
    assert provider.received_observations[1].status == "DENIED"
    assert provider.received_context[1][0].status == "DENIED"


def test_malformed_arguments_are_rejected_and_loop_continues():
    provider = ScriptedProvider(
        [tool_call_response(arguments={"value": 123}), STOP_SIGNAL]
    )

    decision, trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert decision is None
    assert trace[1].payload["status"] == "REJECTED"
    assert trace[-1].kind == "loop_stopped"
    assert provider.received_observations[1].status == "REJECTED"
    assert provider.received_context[1][0].status == "REJECTED"


def test_controlled_tool_error_is_recorded_and_loop_continues():
    provider = ScriptedProvider(
        [tool_call_response(arguments={"fail": True}), STOP_SIGNAL]
    )

    decision, trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert decision is None
    assert trace[1].payload["status"] == "ERROR"
    assert trace[-1].kind == "loop_stopped"
    assert provider.received_observations[1].status == "ERROR"
    assert provider.received_context[1][0].status == "ERROR"


def test_tool_trace_order_sequences_and_logical_turn_indexes():
    decision, trace = run(
        incident(),
        ScriptedProvider([tool_call_response(), STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=2,
    )

    assert decision is None
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

    first_decision, first = run(
        incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2
    )
    second_decision, second = run(
        incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=2
    )

    assert first_decision is None
    assert second_decision is None
    assert first == second


def test_malformed_tool_call_json_is_rejected_without_executor_dispatch():
    provider = ScriptedProvider([TOOL_CALL_PREFIX + "{not-json", STOP_SIGNAL])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
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

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
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

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
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

    decision, trace = run(incident(), provider, executor, max_turns=3)

    assert decision is None
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

    matched_decision, _ = run(
        incident(),
        StateAwareFakeProvider(**provider_arguments),
        matched_executor,
        max_turns=3,
    )
    unmatched_decision, _ = run(
        incident(),
        StateAwareFakeProvider(**provider_arguments),
        unmatched_executor,
        max_turns=3,
    )

    assert matched_decision is None
    assert unmatched_decision is None
    assert matched_executor.calls[0] == unmatched_executor.calls[0]
    assert matched_executor.calls[1].arguments == {"value": "matched-path"}
    assert unmatched_executor.calls[1].arguments == {"value": "unmatched-path"}


@pytest.mark.parametrize(
    ("submission", "expected"),
    [
        (
            {
                "disposition": "NO_REPAIR",
                "root_cause_summary": "The source data reflects a legitimate change.",
            },
            InvestigationDecision(
                disposition=Disposition.NO_REPAIR,
                root_cause_id=None,
                root_cause_summary="The source data reflects a legitimate change.",
            ),
        ),
        (
            {
                "disposition": "ESCALATE",
                "root_cause_id": "missing-authority",
                "root_cause_summary": "An authoritative receipt is unavailable.",
            },
            InvestigationDecision(
                disposition=Disposition.ESCALATE,
                root_cause_id="missing-authority",
                root_cause_summary="An authoritative receipt is unavailable.",
            ),
        ),
        (
            {
                "disposition": "REPAIR",
                "root_cause_id": "double-normalization",
                "root_cause_summary": "The amount was normalized twice.",
                "repair_id": "repair-normalization",
                "patch": {"stg_orders.sql": "amount_cents / 100"},
            },
            InvestigationDecision(
                disposition=Disposition.REPAIR,
                root_cause_id="double-normalization",
                root_cause_summary="The amount was normalized twice.",
                repair_id="repair-normalization",
                patch={"stg_orders.sql": "amount_cents / 100"},
            ),
        ),
    ],
)
def test_valid_decision_is_constructed_traced_and_returned(submission, expected):
    provider = ScriptedProvider(
        [DECISION_PREFIX + json.dumps(submission, sort_keys=True)]
    )
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=1)

    assert decision == expected
    assert executor.calls == []
    assert provider.received_observations == (None,)
    assert provider.received_context == ((),)
    assert len(trace) == 1
    assert trace[0].sequence == 0
    assert trace[0].kind == "decision_submitted"
    assert trace[0].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "disposition": expected.disposition.value,
        "root_cause_id": expected.root_cause_id,
        "root_cause_summary": expected.root_cause_summary,
        "repair_id": expected.repair_id,
        "patch": expected.patch,
    }


def test_stop_still_returns_none_decision():
    decision, trace = run(
        incident(),
        ScriptedProvider([STOP_SIGNAL]),
        FakeToolExecutor(),
        max_turns=1,
    )

    assert decision is None
    assert [event.kind for event in trace] == ["loop_stopped"]


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (DECISION_PREFIX + "{not-json", "decision must be valid JSON"),
        (DECISION_PREFIX + "[]", "decision must be an object"),
        (
            DECISION_PREFIX + json.dumps({"root_cause_summary": "A reason"}),
            "decision is missing disposition",
        ),
        (
            decision_response(disposition="UNKNOWN"),
            "decision has invalid disposition",
        ),
        (
            DECISION_PREFIX + json.dumps({"disposition": "NO_REPAIR"}),
            "decision is missing root_cause_summary",
        ),
        (
            decision_response(root_cause_summary=123),
            "root_cause_summary must be a string",
        ),
        (
            decision_response(root_cause_id=123),
            "root_cause_id must be a string or null",
        ),
        (
            decision_response(repair_id=123),
            "repair_id must be a string or null",
        ),
        (
            decision_response(patch=[]),
            "patch must be an object",
        ),
    ],
)
def test_structurally_invalid_decision_is_rejected_and_loop_continues(
    response,
    reason,
):
    provider = ScriptedProvider([response, STOP_SIGNAL])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
    assert executor.calls == []
    assert provider.received_observations == (None, None)
    assert provider.received_context == ((), ())
    assert [event.kind for event in trace] == [
        "decision_rejected",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == [0, 1]
    assert trace[0].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "reason": reason,
    }


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (
            decision_response(root_cause_summary=""),
            "every decision must explain itself in root_cause_summary",
        ),
        (
            decision_response(
                disposition="REPAIR",
                root_cause_summary="A repair is required.",
            ),
            "a REPAIR decision must carry a repair_id and a patch",
        ),
        (
            decision_response(repair_id="not-allowed"),
            "only a REPAIR decision may carry a repair_id or a patch",
        ),
    ],
)
def test_contract_invalid_decision_is_rejected_without_duplicating_invariants(
    response,
    reason,
):
    provider = ScriptedProvider([response, STOP_SIGNAL])

    decision, trace = run(
        incident(),
        provider,
        FakeToolExecutor(),
        max_turns=2,
    )

    assert decision is None
    assert trace[0].kind == "decision_rejected"
    assert trace[0].payload["reason"] == reason
    assert trace[-1].kind == "loop_stopped"


def test_decision_consumes_one_turn_and_stops_provider_immediately():
    provider = ScriptedProvider([decision_response(), "unused response"])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=1)

    assert decision is not None
    assert [event.payload["turn_index"] for event in trace] == [0]
    assert executor.calls == []
    assert provider.respond() == "unused response"


def test_decision_on_final_permitted_turn_succeeds():
    provider = ScriptedProvider(["ordinary", decision_response()])

    decision, trace = run(
        incident(),
        provider,
        FakeToolExecutor(),
        max_turns=2,
    )

    assert decision is not None
    assert [event.kind for event in trace] == ["model_turn", "decision_submitted"]
    assert [event.payload["turn_index"] for event in trace] == [0, 1]


def test_invalid_decision_on_final_permitted_turn_reaches_existing_budget_error():
    provider = ScriptedProvider([DECISION_PREFIX + "{not-json", decision_response()])
    executor = FakeToolExecutor()

    with pytest.raises(TurnBudgetExceededError) as raised:
        run(incident(), provider, executor, max_turns=1)

    assert executor.calls == []
    assert [event.kind for event in raised.value.trace] == [
        "decision_rejected",
        "budget_exceeded",
    ]
    assert [event.sequence for event in raised.value.trace] == [0, 1]
    assert [event.payload["turn_index"] for event in raised.value.trace] == [0, 1]
    assert provider.respond().startswith(DECISION_PREFIX)


def test_accumulated_state_is_available_before_decision_and_not_changed_by_it():
    provider = ScriptedProvider([tool_call_response(), decision_response()])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    result = executor.results[0]
    assert decision is not None
    assert provider.received_observations == (None, result)
    assert provider.received_context == ((), (result,))
    assert provider.received_observations[1] is result
    assert provider.received_context[1][0] is result
    assert executor.results == [result]
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "decision_submitted",
    ]
    assert [event.sequence for event in trace] == [0, 1, 2]


def test_repeated_decision_runs_are_deterministic():
    script = [decision_response()]

    first = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=1)
    second = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=1)

    assert first == second
