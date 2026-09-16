"""One incident, end to end: investigator, then validation, on a harness-owned trace.

The runtime is the only component that sees every boundary crossing, so it — not the
investigator, not the tool layer — writes the trace and counts from it. An investigator
cannot flatter its own efficiency because it never reports a number: it only makes calls,
and the runtime records each one on the way through.

It knows A, B and C only as the three protocols below. Anything that satisfies them runs:
the scripted components in `fakes.py` today, the real packages when they exist.
"""
from __future__ import annotations

import time
import traceback
from typing import Protocol

from ..contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    ToolCall,
    ToolResult,
    TraceEvent,
    ValidationResult,
)
from ..reporting.record import RunRecord, provenance, strict


class Tools(Protocol):
    """The tool layer: the investigator's entire view of the world, allowed to refuse."""

    def execute(self, call: ToolCall) -> ToolResult: ...


class Investigator(Protocol):
    """The agent. It is handed the incident and a tool boundary, and nothing else."""

    def investigate(self, context: IncidentContext, tools: Tools) -> InvestigationDecision: ...


class Validator(Protocol):
    """The other authority. Rebuilds from frozen inputs; never asks the investigator."""

    def validate(self, context: IncidentContext,
                 decision: InvestigationDecision) -> ValidationResult: ...


class Terminated(Exception):
    """Raised by the loop to end a run without a decision: the model failed, or a bound was
    hit. The classification is the loop's own and travels to the record unchanged — the
    runtime adds no interpretation (plan D-14). `detail` says which failure or which bound,
    in the loop's words."""

    ENDINGS = ("model_failure", "bound_hit")

    def __init__(self, termination: str, detail: str) -> None:
        if termination not in self.ENDINGS:
            raise ValueError(f"termination must be one of {self.ENDINGS}, got {termination!r}")
        super().__init__(f"{termination}: {detail}")
        self.termination, self.detail = termination, detail


class Recorder:
    """The harness-owned trace.

    The five event kinds written here are the walkthrough's — the only vocabulary that
    exists. docs/trace_event_contract.md proposes their successors; when that is agreed,
    this class is the one place that changes.
    """

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def event(self, kind: str, payload: dict[str, object]) -> None:
        self._events.append(TraceEvent(sequence=len(self._events), kind=kind, payload=payload))

    @property
    def trace(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    @property
    def tool_calls(self) -> int:
        """Executed calls. A refusal is the boundary working, not a tool that ran."""
        return sum(1 for e in self._events
                   if e.kind == "tool_result" and e.payload["status"] == "OK")

    def watch(self, tools: Tools) -> Tools:
        return _Watched(tools, self)


class _Watched:
    """The tool boundary as the investigator receives it: every crossing recorded."""

    def __init__(self, inner: Tools, recorder: Recorder) -> None:
        self._inner, self._recorder = inner, recorder

    def execute(self, call: ToolCall) -> ToolResult:
        self._recorder.event("tool_call", {"call_id": call.call_id, "name": call.name,
                                           "arguments": call.arguments})
        result = self._inner.execute(call)
        self._recorder.event("tool_result", {"call_id": result.call_id, "name": result.name,
                                             "status": result.status, "content": result.content})
        return result


def run_incident(label: str, context: IncidentContext, investigator: Investigator,
                 tools: Tools, validator: Validator, *,
                 configuration: dict[str, object]) -> RunRecord:
    """Investigate, validate if a repair was proposed, and return the record — for every way
    a run can end. A submission carries its decision. A run the loop ended carries the loop's
    classification verbatim. Anything else that escapes is our defect: an infrastructure
    failure, with its traceback on stderr, never a lost run. In every case the trace so far
    is the evidence and the counters come from it. Only a REPAIR reaches the validator: the
    contract says so, and this is where it is enforced on the way through."""
    started = time.monotonic()
    recorder = Recorder()
    recorder.event("incident_received", {"incident_id": context.incident_id})
    decision = validation = None
    try:
        decision = investigator.investigate(context, recorder.watch(tools))
        recorder.event("decision_submitted", {"disposition": decision.disposition.value})
        if decision.disposition is Disposition.REPAIR:
            validation = validator.validate(context, decision)
            recorder.event("validation_completed", {"accepted": validation.accepted})
        termination, detail = "submitted", "the investigator committed to a disposition"
    except Terminated as ended:
        decision = validation = None
        termination, detail = ended.termination, ended.detail
    except Exception as defect:  # ours, not the model's: classified and shown, never hidden
        traceback.print_exc()
        decision = validation = None
        termination, detail = "infrastructure_failure", f"{type(defect).__name__}: {defect}"
    return strict(RunRecord(
        label=label, context=context, trace=recorder.trace, termination=termination,
        detail=detail, decision=decision, validation=validation, tool_calls=recorder.tool_calls,
        # No model has run, so no turns and no spend. How the investigator's model traffic
        # reaches this trace is decision 1 of the trace event contract; until it is made,
        # a number here would be invented.
        model_turns=0, api_cost_usd=0.0,
        latency_ms=int((time.monotonic() - started) * 1000),
        configuration=dict(configuration), provenance=provenance("runtime")))
