"""Minimal investigator loop driven by an explicit provider stop signal.

The grammar is closed: a response is `<TOOL_CALL>` JSON, `<DECISION>` JSON, or `<STOP>`.
Anything else — another tag, malformed JSON, a decision that fails the contract or the
evidence gate, naked prose — is an invalid submission: recorded as a durable
`decision_rejected` event with a class, a bounded reason and the submission's digest, the
reason returned to the model once, and the loop continues under its bounds. No form is
special-cased and nothing is reinterpreted as a decision (trace contract, row 6).

Durable events are emitted into the runtime's recorder as they happen, through `sink`, so
the runtime's record is the one history; the trace this function returns is the loop's own
local account, for its tests and diagnostics, and agrees with the record on every durable
fact.
"""

import hashlib
import json
import re
from typing import Protocol

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

# A rejection's reason is bounded text beside a structured class; the submission itself is
# carried by digest and length — its text is the provider boundary's to record.
REJECTION_REASON_CHARS = 240
INVALID_ENVELOPE = ("not one of the three message forms — <TOOL_CALL>{...}, <DECISION>{...} or "
                    "<STOP> — so it was recorded as rejected and nothing acted on it; send exactly "
                    "one form, starting at the first character")
REJECTION_CLASSES = ("invalid_envelope", "invalid_decision", "evidence_gate")


class EventSink(Protocol):
    """Where durable events go as they happen: the runtime's recorder."""

    def event(self, kind: str, payload: dict[str, object]) -> None: ...


def _body(response: str, prefix: str) -> str:
    """The JSON after a protocol tag. Chat models close the tag they opened —
    `<DECISION>{...}</DECISION>` — and a closing tag is not part of the JSON, so a
    matching one at the end is dropped. Nothing else is repaired."""
    body = response.removeprefix(prefix).rstrip()
    closing = "</" + prefix[1:]
    if body.endswith(closing):
        body = body[: -len(closing)]
    return body

_CREDENTIAL_PATTERN = re.compile(
    # API-key prefixes are deliberately case-sensitive; HTTP auth schemes are not.
    r"(?<![A-Za-z0-9_*-])sk-(?:"
    r"[A-Za-z0-9_-]{16,}"
    r"|(?=[A-Za-z0-9_*-]*\*)[A-Za-z0-9_*-]{8,}"
    r")(?![A-Za-z0-9_*-])"
    r"|(?<![A-Za-z0-9._~+/=-])"
    r"(?i:Bearer)[ \t]+[A-Za-z0-9._~+/=-]{16,}(?![A-Za-z0-9._~+/=-])"
)


def _redact_secrets(text: str) -> str:
    """Redact narrow credential shapes from provider-derived public failure reasons."""
    return _CREDENTIAL_PATTERN.sub("[REDACTED]", text)


def _rejection(incident: IncidentContext, turn_index: int, rejection_class: str, reason: str,
               response: str) -> dict[str, object]:
    """The durable fact of an invalid submission: enough to reconstruct what happened, in
    structure, without the submission's text — that is the provider boundary's record."""
    assert rejection_class in REJECTION_CLASSES
    return {
        "incident_id": incident.incident_id,
        "turn_index": turn_index,
        "rejection_class": rejection_class,
        "reason": reason[:REJECTION_REASON_CHARS],
        "submission_sha256": hashlib.sha256(response.encode("utf-8")).hexdigest(),
        "submission_chars": len(response),
    }


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
    sink: EventSink | None = None,
) -> tuple[InvestigationDecision | None, tuple[TraceEvent, ...]]:
    """Run model turns until the provider returns the explicit stop signal.

    `sink`, when the runtime gives one, receives every durable event the loop alone can
    know — a rejected submission — the moment it happens. Tool calls, observations,
    model requests and the submission are recorded at their own boundaries by the runtime.
    """
    if isinstance(max_turns, bool) or not isinstance(max_turns, int) or max_turns < 0:
        raise ValueError("max_turns must be a non-negative integer")

    trace: list[TraceEvent] = []
    turns_taken = 0
    observation: ToolResult | None = None
    state = InvestigationState()
    pending_rejection: dict[str, str] | None = None

    def record(kind: str, payload: dict[str, object], *, durable: bool = False) -> None:
        trace.append(TraceEvent(sequence=len(trace), kind=kind, payload=payload))
        if sink is not None and durable:
            sink.event(kind, payload)

    def reject(turn_index: int, rejection_class: str, reason: str, response: str) -> None:
        nonlocal pending_rejection
        payload = _rejection(incident, turn_index, rejection_class, reason, response)
        record("decision_rejected", payload, durable=True)
        # the same reason goes back to the model, once, with the next request
        pending_rejection = {"class": rejection_class, "reason": payload["reason"]}

    while True:
        turn_index = turns_taken
        if turns_taken >= max_turns:
            record("budget_exceeded", {
                "incident_id": incident.incident_id,
                "turn_index": turn_index,
                "bound": "max_turns",
                "limit": max_turns,
            })
            raise TurnBudgetExceededError(max_turns, tuple(trace))

        kwargs = {"rejection": pending_rejection} if pending_rejection else {}
        pending_rejection = None
        try:
            response = provider.respond(
                observation=observation,
                observations=state.observations,
                **kwargs,
            )
        except ScriptExhaustedError:
            raise
        except Exception as error:
            reason = _redact_secrets(f"{type(error).__name__}: {error}")
            record("provider_failure", {
                "incident_id": incident.incident_id,
                "turn_index": turn_index,
                "reason": reason,
            })
            raise ProviderFailureError(reason, tuple(trace)) from error

        if not isinstance(response, str):
            reason = f"provider returned {type(response).__name__}, expected str"
            record("provider_failure", {
                "incident_id": incident.incident_id,
                "turn_index": turn_index,
                "reason": reason,
            })
            raise ProviderFailureError(reason, tuple(trace))

        observation = None
        turns_taken += 1

        if response == STOP_SIGNAL:
            record("loop_stopped", {
                "incident_id": incident.incident_id,
                "turn_index": turn_index,
                "reason": "explicit_stop",
            })
            return None, tuple(trace)

        if response.startswith(DECISION_PREFIX):
            try:
                decision = _parse_decision(_body(response, DECISION_PREFIX))
            except (TypeError, ValueError) as error:
                reject(turn_index, "invalid_decision", str(error), response)
                continue

            if (
                decision.disposition in (Disposition.REPAIR, Disposition.NO_REPAIR)
                and not state.observations
            ):
                reject(turn_index, "evidence_gate",
                       f"{decision.disposition.value} requires at least one observed tool result",
                       response)
                continue
            # a citation resolves to a successful tool result this model received, or it is
            # not a citation (trace contract row 3): the ids are the tool layer's, never the
            # model's, and one character off is one it never saw
            received = {r.content.get("evidence_id") for r in state.observations if r.ok}
            unresolved = [ref for ref in decision.evidence_refs if ref not in received]
            if unresolved:
                reject(turn_index, "evidence_gate",
                       f"cites evidence this run never observed: {', '.join(unresolved)}; cite "
                       "only the evidence_id of tool results you received", response)
                continue

            record("decision_submitted", {
                "incident_id": incident.incident_id,
                "turn_index": turn_index,
                "disposition": decision.disposition.value,
                "root_cause_id": decision.root_cause_id,
                "root_cause_summary": decision.root_cause_summary,
                "repair_id": decision.repair_id,
                "patch": decision.patch,
                "evidence_refs": list(decision.evidence_refs),
            })
            return decision, tuple(trace)

        if response.startswith(TOOL_CALL_PREFIX):
            call_id = f"tool-call-{turn_index}"
            try:
                intent = json.loads(_body(response, TOOL_CALL_PREFIX))
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
            record("tool_call", {
                "incident_id": incident.incident_id,
                "turn_index": turn_index,
                "call_id": call.call_id,
                "name": call.name,
                "arguments": call.arguments,
            })

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
            record("tool_result", {
                "incident_id": incident.incident_id,
                "turn_index": turn_index,
                "call_id": result.call_id,
                "name": result.name,
                "status": result.status,
                "content": result.content,
            })
            state = InvestigationState(observations=(*state.observations, result))
            observation = result
            continue

        # none of the three forms: an invalid submission, whatever it looks like
        reject(turn_index, "invalid_envelope", INVALID_ENVELOPE, response)


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
    if patch is None:          # "patch": null — a decision that changes nothing carries none
        patch = {}
    if not isinstance(root_cause_summary, str):
        raise ValueError("root_cause_summary must be a string")
    if root_cause_id is not None and not isinstance(root_cause_id, str):
        raise ValueError("root_cause_id must be a string or null")
    if repair_id is not None and not isinstance(repair_id, str):
        raise ValueError("repair_id must be a string or null")
    if not isinstance(patch, dict):
        raise ValueError("patch must be an object")
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in patch.items()):
        raise ValueError("patch must map each path to its new contents, as text")
    refs = submission.get("evidence_refs", [])
    if refs is None:               # "evidence_refs": null — a decision that cites nothing
        refs = []
    if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
        raise ValueError("evidence_refs must be a list of evidence ids, as text")

    return InvestigationDecision(
        disposition=disposition,
        root_cause_id=root_cause_id,
        root_cause_summary=root_cause_summary,
        repair_id=repair_id,
        patch=patch,
        evidence_refs=tuple(refs),
    )
