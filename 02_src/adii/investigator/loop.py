"""Minimal investigator loop driven by an explicit provider stop signal."""

import json

from ..contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    ToolCall,
    ToolResult,
    TraceEvent,
)
from .provider import ScriptExhaustedError
from .state import InvestigationState

STOP_SIGNAL: str = "<STOP>"
TOOL_CALL_PREFIX: str = "<TOOL_CALL>"
DECISION_PREFIX: str = "<DECISION>"




class TurnBudgetExceededError(RuntimeError):
    """Raised when the investigator cannot start another model turn."""

    def __init__(self, limit: int, trace: tuple[TraceEvent, ...]) -> None:
        self.limit = limit
        self.trace = trace
        super().__init__(f"model-turn budget exceeded: max_turns={limit}")


class ProviderFailureError(RuntimeError):
    """Raised when the provider fails at its runtime boundary."""

    def __init__(self, reason: str, trace: tuple[TraceEvent, ...]) -> None:
        self.reason = reason
        self.trace = trace
        super().__init__(f"provider failure: {reason}")


def run(
    incident: IncidentContext,
    provider,
    executor,
    *,
    max_turns: int,
) -> tuple[InvestigationDecision | None, tuple[TraceEvent, ...]]:
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

        try:
            response = provider.respond(
                observation=observation,
                observations=state.observations,
            )
        except ScriptExhaustedError:
            raise
        except Exception as error:
            reason = f"{type(error).__name__}: {error}"
            trace.append(
                TraceEvent(
                    sequence=len(trace),
                    kind="provider_failure",
                    payload={
                        "incident_id": incident.incident_id,
                        "turn_index": turn_index,
                        "reason": reason,
                    },
                )
            )
            raise ProviderFailureError(reason, tuple(trace)) from error

        if not isinstance(response, str):
            reason = f"provider returned {type(response).__name__}, expected str"
            trace.append(
                TraceEvent(
                    sequence=len(trace),
                    kind="provider_failure",
                    payload={
                        "incident_id": incident.incident_id,
                        "turn_index": turn_index,
                        "reason": reason,
                    },
                )
            )
            raise ProviderFailureError(reason, tuple(trace))

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
            return None, tuple(trace)

        if response.startswith(DECISION_PREFIX):
            try:
                decision = _parse_decision(response.removeprefix(DECISION_PREFIX))
            except (TypeError, ValueError) as error:
                trace.append(
                    TraceEvent(
                        sequence=len(trace),
                        kind="decision_rejected",
                        payload={
                            "incident_id": incident.incident_id,
                            "turn_index": turn_index,
                            "reason": str(error),
                        },
                    )
                )
                continue

            if (
                decision.disposition in (Disposition.REPAIR, Disposition.NO_REPAIR)
                and not state.observations
            ):
                trace.append(
                    TraceEvent(
                        sequence=len(trace),
                        kind="decision_rejected",
                        payload={
                            "incident_id": incident.incident_id,
                            "turn_index": turn_index,
                            "reason": (
                                f"{decision.disposition.value} requires at least one "
                                "observed tool result"
                            ),
                        },
                    )
                )
                continue

            trace.append(
                TraceEvent(
                    sequence=len(trace),
                    kind="decision_submitted",
                    payload={
                        "incident_id": incident.incident_id,
                        "turn_index": turn_index,
                        "disposition": decision.disposition.value,
                        "root_cause_id": decision.root_cause_id,
                        "root_cause_summary": decision.root_cause_summary,
                        "repair_id": decision.repair_id,
                        "patch": decision.patch,
                    },
                )
            )
            return decision, tuple(trace)

        if response.startswith(TOOL_CALL_PREFIX):
            call_id = f"tool-call-{turn_index}"
            try:
                intent = json.loads(response.removeprefix(TOOL_CALL_PREFIX))
            except (json.JSONDecodeError, RecursionError):
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
                try:
                    result = executor.execute(call)
                except Exception as error:
                    result = ToolResult(
                        call_id=call.call_id,
                        name=call.name,
                        status="ERROR",
                        content={
                            "error": (
                                f"executor raised {type(error).__name__}: {error}"
                            )
                        },
                    )
                if not isinstance(result, ToolResult):
                    result = ToolResult(
                        call_id=call.call_id,
                        name=call.name,
                        status="ERROR",
                        content={
                            "error": (
                                f"executor returned {type(result).__name__}, "
                                "expected ToolResult"
                            )
                        },
                    )
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


def _parse_decision(payload: str) -> InvestigationDecision:
    try:
        submission = json.loads(payload)
    except (json.JSONDecodeError, RecursionError):
        raise ValueError("decision must be valid JSON") from None

    if not isinstance(submission, dict):
        raise ValueError("decision must be an object")
    if "disposition" not in submission:
        raise ValueError("decision is missing disposition")
    try:
        disposition = Disposition(submission["disposition"])
    except (TypeError, ValueError):
        raise ValueError("decision has invalid disposition") from None
    if "root_cause_summary" not in submission:
        raise ValueError("decision is missing root_cause_summary")

    root_cause_summary = submission["root_cause_summary"]
    root_cause_id = submission.get("root_cause_id")
    repair_id = submission.get("repair_id")
    patch = submission.get("patch", {})
    if not isinstance(root_cause_summary, str):
        raise ValueError("root_cause_summary must be a string")
    if root_cause_id is not None and not isinstance(root_cause_id, str):
        raise ValueError("root_cause_id must be a string or null")
    if repair_id is not None and not isinstance(repair_id, str):
        raise ValueError("repair_id must be a string or null")
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")

    return InvestigationDecision(
        disposition=disposition,
        root_cause_id=root_cause_id,
        root_cause_summary=root_cause_summary,
        repair_id=repair_id,
        patch=patch,
    )
