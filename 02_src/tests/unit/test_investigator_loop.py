import hashlib
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
    INVALID_ENVELOPE,
    REJECTION_REASON_CHARS,
    STOP_SIGNAL,
    TOOL_CALL_PREFIX,
    ProviderFailureError,
    TurnBudgetExceededError,
    _redact_secrets,
    run,
)
from adii.investigator.provider import ScriptedProvider, ScriptExhaustedError
from adii.investigator.state import InvestigationState

from .fakes import (
    FakeToolExecutor,
    NonStringProvider,
    NonToolResultExecutor,
    RaisingProvider,
    RaisingToolExecutor,
    StateAwareFakeProvider,
)


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
    # plain prose is none of the three forms: an invalid submission, recorded by class and
    # digest — the text itself is the provider boundary's to record
    assert [event.kind for event in trace] == ["decision_rejected", "decision_rejected",
                                               "loop_stopped"]
    assert [event.payload["rejection_class"] for event in trace[:-1]] == \
        ["invalid_envelope", "invalid_envelope"]
    assert [event.payload["submission_sha256"] for event in trace[:-1]] == \
        [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in ("first", "second")]
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
    assert [event.kind for event in trace] == ["decision_rejected", "loop_stopped"]


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
        "decision_rejected",
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
    ("submission", "expected", "requires_observation"),
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
            True,
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
            False,
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
            True,
        ),
    ],
)
def test_valid_decision_is_constructed_traced_and_returned(
    submission,
    expected,
    requires_observation,
):
    decision_submission = DECISION_PREFIX + json.dumps(submission, sort_keys=True)
    script = (
        [tool_call_response(), decision_submission]
        if requires_observation
        else [decision_submission]
    )
    provider = ScriptedProvider(script)
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=len(script))

    assert decision == expected
    if requires_observation:
        result = executor.results[0]
        assert provider.received_observations == (None, result)
        assert provider.received_context == ((), (result,))
        assert provider.received_context[1][0] is result
        assert [event.kind for event in trace] == [
            "tool_call",
            "tool_result",
            "decision_submitted",
        ]
    else:
        assert executor.calls == []
        assert provider.received_observations == (None,)
        assert provider.received_context == ((),)
        assert [event.kind for event in trace] == ["decision_submitted"]
    assert [event.sequence for event in trace] == list(range(len(trace)))
    assert trace[-1].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": len(script) - 1,
        "disposition": expected.disposition.value,
        "root_cause_id": expected.root_cause_id,
        "root_cause_summary": expected.root_cause_summary,
        "repair_id": expected.repair_id,
        "patch": expected.patch,
        "evidence_refs": list(expected.evidence_refs),
    }


MINTED = "ev-0123456789abcdef"


class MintingExecutor:
    """The tool layer as the loop meets it: a successful result carries the id it minted."""

    def execute(self, call: ToolCall) -> ToolResult:
        return ToolResult(call.call_id, call.name, "OK", {"value": 1, "evidence_id": MINTED})


def test_a_decision_citing_an_observation_it_received_carries_the_citation():
    """Trace contract row 3: the citation is the tool layer's id, copied by the model, and
    it travels on the decision and in the loop's own submission event."""
    provider = ScriptedProvider([tool_call_response(),
                                 decision_response(evidence_refs=[MINTED])])
    decision, trace = run(incident(), provider, MintingExecutor(), max_turns=2)
    assert decision.evidence_refs == (MINTED,)
    assert trace[-1].kind == "decision_submitted"
    assert trace[-1].payload["evidence_refs"] == [MINTED]


@pytest.mark.parametrize("cited", [
    "ev-0123456789abcdee",          # one character off a minted id: never received
    "ev-never-minted",
])
def test_a_citation_to_an_id_the_model_never_received_is_refused_and_told_once(cited):
    """The archived run that cited an id one character off a minted one and nothing
    noticed (Phase 6) is the case: a citation resolves to a successful result this model
    received, or the decision is rejected at the evidence gate with the id named, the
    reason returned once, and a corrected decision accepted on the next turn."""
    provider = ScriptedProvider([tool_call_response(),
                                 decision_response(evidence_refs=[cited]),
                                 decision_response(evidence_refs=[MINTED])])
    decision, trace = run(incident(), provider, MintingExecutor(), max_turns=3)
    assert decision.evidence_refs == (MINTED,)
    assert [e.kind for e in trace] == ["tool_call", "tool_result", "decision_rejected",
                                       "decision_submitted"]
    rejected = trace[2].payload
    assert rejected["rejection_class"] == "evidence_gate"
    assert rejected["reason"].startswith(f"cites evidence this run never observed: {cited};")
    assert provider.received_rejections == (None, None, {"class": "evidence_gate",
                                                          "reason": rejected["reason"]})


def test_a_refused_tool_result_minted_nothing_a_decision_can_cite():
    """A DENIED result is an observation for the minimum-observation rule and carries no
    evidence id: citing anything after it alone is citing what was never minted."""
    provider = ScriptedProvider([tool_call_response(name="no_such_tool"),
                                 decision_response(evidence_refs=[MINTED]), STOP_SIGNAL])
    executor = FakeToolExecutor()
    decision, trace = run(incident(), provider, executor, max_turns=3)
    assert executor.results[0].status == "DENIED" and decision is None
    assert [e.kind for e in trace] == ["tool_call", "tool_result", "decision_rejected",
                                       "loop_stopped"]
    assert trace[2].payload["rejection_class"] == "evidence_gate"


@pytest.mark.parametrize(("refs", "reason"), [
    ("ev-0123456789abcdef", "evidence_refs must be a list of evidence ids, as text"),
    ([1, 2], "evidence_refs must be a list of evidence ids, as text"),
    ([MINTED, MINTED], "evidence_refs cites each observation once"),
])
def test_malformed_citations_are_an_invalid_decision(refs, reason):
    provider = ScriptedProvider([tool_call_response(), decision_response(evidence_refs=refs),
                                 STOP_SIGNAL])
    decision, trace = run(incident(), provider, MintingExecutor(), max_turns=3)
    assert decision is None and trace[2].kind == "decision_rejected"
    assert trace[2].payload["rejection_class"] == "invalid_decision"
    assert trace[2].payload["reason"] == reason


@pytest.mark.parametrize(
    "response",
    [
        decision_response(patch=None),
        decision_response() + "</DECISION>",
        decision_response(patch=None) + "</DECISION>\n",
    ],
)
def test_a_decision_with_no_patch_or_a_closed_tag_is_the_decision_it_states(response):
    """What a chat model writes: `"patch": null` for a decision that changes nothing, and
    the tag it opened closed behind the JSON. Neither is a different decision."""
    provider = ScriptedProvider([tool_call_response(), response])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is not None
    assert decision.disposition is Disposition.NO_REPAIR and decision.patch == {}
    assert [event.kind for event in trace][-1] == "decision_submitted"


def test_a_tool_call_with_a_closed_tag_is_dispatched():
    provider = ScriptedProvider([tool_call_response() + "</TOOL_CALL>", STOP_SIGNAL])
    executor = FakeToolExecutor()

    run(incident(), provider, executor, max_turns=2)

    assert len(executor.calls) == 1


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
        (
            decision_response(patch={"ledger": {"day": "2026-03-09", "settled_usd": 91340.0}}),
            "patch must map each path to its new contents, as text",
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
    assert {k: trace[0].payload[k] for k in ("incident_id", "turn_index", "reason")} == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "reason": reason,
    }
    assert trace[0].payload["rejection_class"] == "invalid_decision"


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
    provider = ScriptedProvider(
        [decision_response(disposition="ESCALATE"), "unused response"]
    )
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=1)

    assert decision is not None
    assert [event.payload["turn_index"] for event in trace] == [0]
    assert executor.calls == []
    assert provider.respond() == "unused response"


def test_decision_on_final_permitted_turn_succeeds():
    provider = ScriptedProvider(
        ["ordinary", decision_response(disposition="ESCALATE")]
    )

    decision, trace = run(
        incident(),
        provider,
        FakeToolExecutor(),
        max_turns=2,
    )

    assert decision is not None
    assert [event.kind for event in trace] == ["decision_rejected", "decision_submitted"]
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
    script = [decision_response(disposition="ESCALATE")]

    first = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=1)
    second = run(incident(), ScriptedProvider(script), FakeToolExecutor(), max_turns=1)

    assert first == second


def test_escalate_with_prior_tool_result_is_accepted():
    provider = ScriptedProvider(
        [tool_call_response(), decision_response(disposition="ESCALATE")]
    )
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    result = executor.results[0]
    assert decision is not None
    assert decision.disposition is Disposition.ESCALATE
    assert provider.received_observations == (None, result)
    assert provider.received_context == ((), (result,))
    assert provider.received_context[1][0] is result
    assert trace[-1].kind == "decision_submitted"


@pytest.mark.parametrize(
    ("disposition", "decision_fields"),
    [
        (
            "REPAIR",
            {
                "repair_id": "repair-1",
                "patch": {"stg_orders.sql": "bounded repair"},
            },
        ),
        ("NO_REPAIR", {}),
    ],
)
def test_evidence_required_decision_without_observations_is_rejected_and_continues(
    disposition,
    decision_fields,
):
    provider = ScriptedProvider(
        [
            decision_response(disposition=disposition, **decision_fields),
            STOP_SIGNAL,
        ]
    )
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
    assert executor.calls == []
    assert executor.results == []
    assert provider.received_observations == (None, None)
    assert provider.received_context == ((), ())
    assert [event.kind for event in trace] == [
        "decision_rejected",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == [0, 1]
    assert [event.payload["turn_index"] for event in trace] == [0, 1]
    assert {k: trace[0].payload[k] for k in ("incident_id", "turn_index", "reason")} == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "reason": f"{disposition} requires at least one observed tool result",
    }
    assert trace[0].payload["rejection_class"] == "evidence_gate"


def test_evidence_gate_rejection_does_not_change_state_before_retry():
    submission = decision_response()
    provider = ScriptedProvider([submission, tool_call_response(), submission])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=3)

    result = executor.results[0]
    assert decision is not None
    assert decision.disposition is Disposition.NO_REPAIR
    assert executor.calls == [
        ToolCall(
            call_id="tool-call-1",
            name="fake_tool",
            arguments={"value": "hello"},
        )
    ]
    assert provider.received_observations == (None, None, result)
    assert provider.received_context == ((), (), (result,))
    assert provider.received_context[2][0] is result
    assert [event.kind for event in trace] == [
        "decision_rejected",
        "tool_call",
        "tool_result",
        "decision_submitted",
    ]
    assert [event.sequence for event in trace] == [0, 1, 2, 3]
    assert [event.payload["turn_index"] for event in trace] == [0, 1, 1, 2]


def test_provider_exception_before_first_response_is_traced_and_wrapped():
    provider = RaisingProvider()
    executor = FakeToolExecutor()

    with pytest.raises(ProviderFailureError) as raised:
        run(incident(), provider, executor, max_turns=1)

    assert isinstance(raised.value.__cause__, RuntimeError)
    assert str(raised.value) == (
        "provider failure: RuntimeError: deterministic provider failure"
    )
    assert executor.calls == []
    assert raised.value.trace[0].kind == "provider_failure"
    assert raised.value.trace[0].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "reason": "RuntimeError: deterministic provider failure",
    }
    assert [event.sequence for event in raised.value.trace] == [0]


def test_provider_failure_redacts_openai_like_secret_in_error_and_trace():
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz012345"
    original = RuntimeError(f"request rejected for {secret}. status=401")

    with pytest.raises(ProviderFailureError) as raised:
        run(
            incident(),
            RaisingProvider(error=original),
            FakeToolExecutor(),
            max_turns=1,
        )

    expected_reason = "RuntimeError: request rejected for [REDACTED]. status=401"
    assert raised.value.reason == expected_reason
    assert secret not in raised.value.reason
    assert str(raised.value) == f"provider failure: {expected_reason}"
    assert raised.value.trace[0].kind == "provider_failure"
    assert raised.value.trace[0].sequence == 0
    assert raised.value.trace[0].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "reason": expected_reason,
    }
    assert secret not in raised.value.trace[0].payload["reason"]


@pytest.mark.parametrize(
    "secret",
    [
        "sk-****XXXX",
        "sk-Eyftb***************************************99vW",
    ],
)
def test_secret_redaction_covers_real_masked_openai_key_shapes(secret):
    message = f"Incorrect API key provided: {secret}."

    assert _redact_secrets(message) == "Incorrect API key provided: [REDACTED]."


def test_masked_key_is_redacted_from_openai_like_401_failure_and_trace():
    secret = "sk-Eyftb***************************************99vW"
    message = (
        "Error code: 401 - {'error': {'message': 'Incorrect API key provided: "
        f"{secret}', 'type': 'invalid_request_error', 'code': 'invalid_api_key'}}"
    )

    with pytest.raises(ProviderFailureError) as raised:
        run(
            incident(),
            RaisingProvider(error=RuntimeError(message)),
            FakeToolExecutor(),
            max_turns=1,
        )

    trace_reason = raised.value.trace[0].payload["reason"]
    assert isinstance(trace_reason, str)
    assert secret not in raised.value.reason
    assert secret not in trace_reason
    assert "[REDACTED]" in raised.value.reason
    assert "[REDACTED]" in trace_reason
    assert "Error code: 401" in raised.value.reason
    assert "invalid_request_error" in raised.value.reason
    assert "invalid_api_key" in raised.value.reason


def test_provider_failure_redacts_every_credential_like_fragment():
    secrets = (
        "sk-admin-abcdefghijklmnopqrstuvwxyz",
        "sk-svcacct-0123456789_ABCDEFGHIJK",
        "Bearer eyJhbGciOiJIUzI1NiJ9.payload-signature",
    )
    original = RuntimeError(" | ".join(secrets))

    with pytest.raises(ProviderFailureError) as raised:
        run(
            incident(),
            RaisingProvider(error=original),
            FakeToolExecutor(),
            max_turns=1,
        )

    assert raised.value.reason.count("[REDACTED]") == len(secrets)
    assert all(secret not in raised.value.reason for secret in secrets)
    trace_reason = raised.value.trace[0].payload["reason"]
    assert isinstance(trace_reason, str)
    assert trace_reason.count("[REDACTED]") == len(secrets)
    assert all(secret not in trace_reason for secret in secrets)


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER"])
def test_provider_failure_redacts_bearer_token(scheme):
    bearer = f"{scheme} abcdefghijklmnopqrstuvwxyz.0123456789_-/+=="
    original = RuntimeError(f"authorization failed: {bearer}")

    with pytest.raises(ProviderFailureError) as raised:
        run(
            incident(),
            RaisingProvider(error=original),
            FakeToolExecutor(),
            max_turns=1,
        )

    assert raised.value.reason == "RuntimeError: authorization failed: [REDACTED]"
    assert bearer not in raised.value.reason


def test_provider_failure_redaction_preserves_non_credentials_byte_for_byte():
    message = (
        "request=550e8400-e29b-41d4-a716-446655440000 "
        "digest=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855 "
        "call_id=tool-call-12 token=sk-short"
    )

    with pytest.raises(ProviderFailureError) as raised:
        run(
            incident(),
            RaisingProvider(error=RuntimeError(message)),
            FakeToolExecutor(),
            max_turns=1,
        )

    assert raised.value.reason == f"RuntimeError: {message}"
    assert raised.value.trace[0].payload["reason"] == f"RuntimeError: {message}"


def test_provider_failure_preserves_exact_original_exception_as_cause():
    secret = "sk-proj-abcdefghijklmnopqrstuvwxyz012345"
    original = RuntimeError(f"raw provider message includes {secret}")

    with pytest.raises(ProviderFailureError) as raised:
        run(
            incident(),
            RaisingProvider(error=original),
            FakeToolExecutor(),
            max_turns=1,
        )

    assert raised.value.__cause__ is original
    assert str(original) == f"raw provider message includes {secret}"
    assert secret not in raised.value.reason


def test_secret_redaction_is_idempotent():
    text = "RuntimeError: sk-proj-abcdefghijklmnopqrstuvwxyz012345 and [REDACTED]"
    redacted = _redact_secrets(text)

    assert redacted == "RuntimeError: [REDACTED] and [REDACTED]"
    assert _redact_secrets(redacted) == redacted


def test_provider_exception_after_tool_result_preserves_prior_trace_and_state():
    provider = RaisingProvider(tool_call_response())
    executor = FakeToolExecutor()

    with pytest.raises(ProviderFailureError) as raised:
        run(incident(), provider, executor, max_turns=2)

    result = executor.results[0]
    assert provider.received_observations == (None, result)
    assert provider.received_context == ((), (result,))
    assert provider.received_observations[1] is result
    assert provider.received_context[1][0] is result
    assert executor.results == [result]
    assert [event.kind for event in raised.value.trace] == [
        "tool_call",
        "tool_result",
        "provider_failure",
    ]
    assert [event.sequence for event in raised.value.trace] == [0, 1, 2]
    assert raised.value.trace[-1].payload["turn_index"] == 1


def test_script_exhaustion_remains_unwrapped_and_has_no_provider_failure():
    provider = ScriptedProvider(["ordinary"])

    with pytest.raises(ScriptExhaustedError) as raised:
        run(incident(), provider, FakeToolExecutor(), max_turns=2)

    assert raised.value.__cause__ is None
    assert not isinstance(raised.value, ProviderFailureError)


def test_non_string_provider_response_is_a_terminal_provider_failure():
    executor = FakeToolExecutor()

    with pytest.raises(ProviderFailureError) as raised:
        run(incident(), NonStringProvider(123), executor, max_turns=1)

    assert raised.value.__cause__ is None
    assert raised.value.reason == "provider returned int, expected str"
    assert executor.calls == []
    assert raised.value.trace[0].payload == {
        "incident_id": "incident-phase-2",
        "turn_index": 0,
        "reason": "provider returned int, expected str",
    }


def test_provider_failure_is_deterministic_across_identical_runs():
    failures = []
    for _ in range(2):
        with pytest.raises(ProviderFailureError) as raised:
            run(incident(), RaisingProvider(), FakeToolExecutor(), max_turns=1)
        failures.append((str(raised.value), raised.value.trace))

    assert failures[0] == failures[1]


def test_executor_exception_becomes_one_error_result_and_loop_continues():
    provider = ScriptedProvider(
        [tool_call_response(), "continue after executor error", STOP_SIGNAL]
    )
    executor = RaisingToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=3)

    result = provider.received_observations[1]
    assert decision is None
    assert result is not None
    assert result.status == "ERROR"
    assert result.call_id == "tool-call-0"
    assert result.name == "fake_tool"
    assert result.content == {
        "error": "executor raised RuntimeError: deterministic executor failure"
    }
    assert len(executor.calls) == 1
    assert provider.received_observations == (None, result, None)
    assert provider.received_context == ((), (result,), (result,))
    assert provider.received_observations[1] is result
    assert provider.received_context[1][0] is result
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "decision_rejected",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == [0, 1, 2, 3]
    assert trace[1].payload["status"] == "ERROR"


def test_non_tool_result_from_executor_becomes_one_error_observation():
    provider = ScriptedProvider([tool_call_response(), STOP_SIGNAL])
    executor = NonToolResultExecutor({"not": "a ToolResult"})

    decision, trace = run(incident(), provider, executor, max_turns=2)

    result = provider.received_observations[1]
    assert decision is None
    assert result is not None
    assert result.status == "ERROR"
    assert result.call_id == "tool-call-0"
    assert result.name == "fake_tool"
    assert result.content == {
        "error": "executor returned dict, expected ToolResult"
    }
    assert len(executor.calls) == 1
    assert provider.received_context == ((), (result,))
    assert provider.received_context[1][0] is result
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "loop_stopped",
    ]
    assert [event.sequence for event in trace] == [0, 1, 2]


def test_deeply_nested_tool_json_is_rejected_without_executor_dispatch():
    pathological_json = "[" * 5_000 + "0" + "]" * 5_000
    provider = ScriptedProvider([TOOL_CALL_PREFIX + pathological_json, STOP_SIGNAL])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    result = provider.received_observations[1]
    assert decision is None
    assert executor.calls == []
    assert result is not None
    assert result.status == "REJECTED"
    assert [event.kind for event in trace] == [
        "tool_call",
        "tool_result",
        "loop_stopped",
    ]


def test_deeply_nested_decision_json_is_rejected_and_loop_continues():
    # How json.loads fails on this depth is platform-dependent: some interpreters hit
    # RecursionError (invalid JSON), others parse it successfully as a non-dict list.
    # Both are legitimate, already-covered _parse_decision outcomes; only the invariant
    # that the decision is safely rejected and the loop continues is asserted here.
    pathological_json = "[" * 5_000 + "0" + "]" * 5_000
    provider = ScriptedProvider([DECISION_PREFIX + pathological_json, STOP_SIGNAL])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
    assert executor.calls == []
    assert [event.kind for event in trace] == [
        "decision_rejected",
        "loop_stopped",
    ]
    assert trace[0].payload["reason"] in {
        "decision must be valid JSON",
        "decision must be an object",
    }


def test_recursion_error_during_decision_parse_is_reported_as_invalid_json(monkeypatch):
    def _raise_recursion_error(*_args, **_kwargs):
        raise RecursionError("maximum recursion depth exceeded")

    monkeypatch.setattr(json, "loads", _raise_recursion_error)
    provider = ScriptedProvider([DECISION_PREFIX + "{}", STOP_SIGNAL])
    executor = FakeToolExecutor()

    decision, trace = run(incident(), provider, executor, max_turns=2)

    assert decision is None
    assert executor.calls == []
    assert [event.kind for event in trace] == [
        "decision_rejected",
        "loop_stopped",
    ]
    assert trace[0].payload["reason"] == "decision must be valid JSON"


def test_repeated_continuable_parse_failures_end_at_existing_turn_budget():
    pathological_json = "[" * 5_000 + "0" + "]" * 5_000
    provider = ScriptedProvider(
        [
            DECISION_PREFIX + pathological_json,
            TOOL_CALL_PREFIX + pathological_json,
        ]
    )
    executor = FakeToolExecutor()

    with pytest.raises(TurnBudgetExceededError) as raised:
        run(incident(), provider, executor, max_turns=2)

    assert executor.calls == []
    assert [event.kind for event in raised.value.trace] == [
        "decision_rejected",
        "tool_call",
        "tool_result",
        "budget_exceeded",
    ]
    assert [event.sequence for event in raised.value.trace] == [0, 1, 2, 3]
    assert [event.payload["turn_index"] for event in raised.value.trace] == [
        0,
        1,
        1,
        2,
    ]


# ── row 6: every invalid submission is one durable event, its reason returned once ──────

REJECTIONS = [
    '<ESCALATE>{"disposition": "ESCALATE", "root_cause_summary": "x", "repair_id": null}',
    "<DECIDE>{}",
    "",
    "I think the pipeline is broken.",
    "<TOOL_CALL",                                     # the tag, unfinished
]


@pytest.mark.parametrize("response", REJECTIONS)
def test_anything_but_the_three_forms_is_an_invalid_envelope_no_form_special_cased(response):
    provider = ScriptedProvider([response, STOP_SIGNAL])
    decision, trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)
    assert decision is None
    assert [e.kind for e in trace] == ["decision_rejected", "loop_stopped"]
    rejected = trace[0].payload
    assert rejected["rejection_class"] == "invalid_envelope"
    assert rejected["reason"] == INVALID_ENVELOPE
    assert rejected["submission_sha256"] == hashlib.sha256(response.encode("utf-8")).hexdigest()
    assert rejected["submission_chars"] == len(response)
    # the reason went back to the model with the next request, once, and never before
    assert provider.received_rejections == (
        None, {"class": "invalid_envelope", "reason": INVALID_ENVELOPE})


def test_the_reason_is_returned_once_and_a_repeat_is_rejected_again():
    bad = '<ESCALATE>{"disposition": "ESCALATE"}'
    provider = ScriptedProvider([bad, bad, decision_response(disposition="ESCALATE")])
    decision, trace = run(incident(), provider, FakeToolExecutor(), max_turns=3)
    assert decision is not None and decision.disposition is Disposition.ESCALATE
    assert [e.kind for e in trace] == ["decision_rejected", "decision_rejected",
                                       "decision_submitted"]
    assert [r and r["class"] for r in provider.received_rejections] == \
        [None, "invalid_envelope", "invalid_envelope"]


def test_every_rejection_class_carries_the_submissions_digest():
    cases = {
        "invalid_decision": decision_response(root_cause_summary=""),
        "evidence_gate": decision_response(disposition="NO_REPAIR"),
        "invalid_envelope": "<ESCALATE>{}",
    }
    for expected, response in cases.items():
        provider = ScriptedProvider([response, STOP_SIGNAL])
        _, trace = run(incident(), provider, FakeToolExecutor(), max_turns=2)
        assert trace[0].payload["rejection_class"] == expected, expected
        assert trace[0].payload["submission_sha256"] == \
            hashlib.sha256(response.encode("utf-8")).hexdigest()
        assert len(trace[0].payload["reason"]) <= REJECTION_REASON_CHARS


def test_a_sink_receives_every_rejection_as_it_happens_and_nothing_else():
    """The runtime's recorder is the one history: the loop emits the durable events only it
    can know into it, the moment they happen; tool calls, observations and the submission
    are the runtime's own boundaries' to record."""
    class Sink:
        def __init__(self):
            self.events = []

        def event(self, kind, payload):
            self.events.append((kind, payload))

    sink = Sink()
    provider = ScriptedProvider(["prose", tool_call_response(), decision_response()])
    decision, trace = run(incident(), provider, FakeToolExecutor(), max_turns=3, sink=sink)
    assert decision is not None
    assert [k for k, _ in sink.events] == ["decision_rejected"]
    assert sink.events[0][1] == next(e.payload for e in trace if e.kind == "decision_rejected")
