"""Minimal investigator loop driven by an explicit provider stop signal."""

import json

from ..contracts import IncidentContext, ToolCall, ToolResult, TraceEvent
from .state import InvestigationState

STOP_SIGNAL: str = "<STOP>"
TOOL_CALL_PREFIX: str = "<TOOL_CALL>"


class TurnBudgetExceededError(RuntimeError):
    """Raised when the investigator cannot start another model turn."""

    def __init__(self, limit: int, trace: tuple[TraceEvent, ...]) -> None:
        self.limit = limit
        self.trace = trace
        super().__init__(f"model-turn budget exceeded: max_turns={limit}")


def run(
    incident: IncidentContext,
    provider,
    executor,
    *,
    max_turns: int,
) -> tuple[TraceEvent, ...]:
    """Run model turns until the provider returns the explicit stop signal."""
    if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 0:
        raise ValueError("max_turns must be a non-negative integer")

    trace: list[TraceEvent] = []
    turns_taken = 0
    observation: ToolResult | None = None
    state = InvestigationState()

    while True:
        turn_index = turns_taken
        if turns_taken >= max_turns:
            trace.append(
                TraceEvent(
                    sequence=len(trace),
                    kind="budget_exceeded",
                    payload={
                        "incident_id": incident.incident_id,
                        "turn_index": turn_index,
                        "bound": "max_turns",
                        "limit": max_turns,
                    },
                )
            )
            raise TurnBudgetExceededError(max_turns, tuple(trace))

        response = provider.respond(
            observation=observation,
            observations=state.observations,
        )
        observation = None
        turns_taken += 1

        if response == STOP_SIGNAL:
            trace.append(
                TraceEvent(
                    sequence=len(trace),
                    kind="loop_stopped",
                    payload={
                        "incident_id": incident.incident_id,
                        "turn_index": turn_index,
                        "reason": "explicit_stop",
                    },
                )
            )
            return tuple(trace)

        if response.startswith(TOOL_CALL_PREFIX):
            call_id = f"tool-call-{turn_index}"
            try:
                intent = json.loads(response.removeprefix(TOOL_CALL_PREFIX))
            except json.JSONDecodeError:
                intent = None

            name = intent.get("name") if isinstance(intent, dict) else None
            arguments = (
                intent.get("arguments", {}) if isinstance(intent, dict) else None
            )
            valid_envelope = (
                isinstance(name, str)
                and bool(name.strip())
                and isinstance(arguments, dict)
            )
            call = ToolCall(
                call_id=call_id,
                name=name if isinstance(name, str) and name.strip() else "<invalid>",
                arguments=arguments if isinstance(arguments, dict) else {},
            )
            trace.append(
                TraceEvent(
                    sequence=len(trace),
                    kind="tool_call",
                    payload={
                        "incident_id": incident.incident_id,
                        "turn_index": turn_index,
                        "call_id": call.call_id,
                        "name": call.name,
                        "arguments": call.arguments,
                    },
                )
            )

            if valid_envelope:
                result = executor.execute(call)
            else:
                result = ToolResult(
                    call_id=call.call_id,
                    name=call.name,
                    status="REJECTED",
                    content={"error": "invalid tool-call envelope"},
                )
            trace.append(
                TraceEvent(
                    sequence=len(trace),
                    kind="tool_result",
                    payload={
                        "incident_id": incident.incident_id,
                        "turn_index": turn_index,
                        "call_id": result.call_id,
                        "name": result.name,
                        "status": result.status,
                        "content": result.content,
                    },
                )
            )
            state = InvestigationState(observations=(*state.observations, result))
            observation = result
            continue

        trace.append(
            TraceEvent(
                sequence=len(trace),
                kind="model_turn",
                payload={
                    "incident_id": incident.incident_id,
                    "turn_index": turn_index,
                    "response": response,
                },
            )
        )
