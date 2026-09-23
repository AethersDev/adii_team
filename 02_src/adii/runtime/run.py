"""One incident, end to end: investigator, then validation, on a harness-owned trace.

The runtime is the only component that sees every boundary crossing, so it — not the
investigator, not the tool layer — writes the trace and counts from it. An investigator
cannot flatter its own efficiency because it never reports a number: it only makes calls,
and the runtime records each one on the way through.

It knows A, B and C only as the three protocols below. Anything that satisfies them runs:
the scripted components in `scripted.py` today, the real packages when they exist.
"""
from __future__ import annotations

import json
import time
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from ..contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    RepairAuthorization,
    ToolCall,
    ToolResult,
    TraceEvent,
    ValidationResult,
)
from ..reporting.record import RunRecord, provenance, strict, unresolved_citations


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


def authorize(context: IncidentContext, decision: InvestigationDecision) -> RepairAuthorization:
    """The runtime's own fact about a REPAIR: is every path the patch touches one the incident
    permitted? Sets, whole — one target outside `permitted_write_paths` denies the patch
    entire, because a repair is applied whole or not at all. It never asks whether the patch
    works: that is the validator's question, established independently of this one
    (m7_validation_integration.md, row 4). Nothing executes on either answer."""
    if decision.disposition is not Disposition.REPAIR:
        raise ValueError("only a REPAIR has targets to authorize; nothing is fabricated for "
                         f"{decision.disposition.value}")
    checked = tuple(decision.patch)
    permitted = set(context.permitted_write_paths)
    denied = tuple(path for path in checked if path not in permitted)
    return RepairAuthorization(authorized=not denied, checked_paths=checked, denied_paths=denied,
                               reason_code="target_not_permitted" if denied else None)


class Terminated(Exception):
    """Raised by the loop to end a run without a decision: the model failed, or a bound was
    hit. The classification is the loop's own and travels to the record unchanged — the
    runtime adds no interpretation (plan D-14). `detail` says which failure or which bound,
    in the loop's words."""

    ENDINGS = ("model_failure", "bound_hit", "infrastructure_failure")

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

    def __init__(self, sink: Path | None = None) -> None:
        """`sink`: a file every event is appended to the moment it happens, one JSON line
        each, flushed — the live view of a run in progress, and the diagnostic evidence a
        killed run leaves behind. The record written at the end is still the authority."""
        self._events: list[TraceEvent] = []
        self._sink = sink.open("a", encoding="utf-8", newline="\n") if sink else None

    def event(self, kind: str, payload: dict[str, object]) -> None:
        event = TraceEvent(sequence=len(self._events), kind=kind, payload=payload)
        self._events.append(event)
        if self._sink:
            self._sink.write(json.dumps({"sequence": event.sequence, "kind": kind,
                                         "payload": payload}, allow_nan=False) + "\n")
            self._sink.flush()

    @property
    def trace(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)

    @property
    def tool_calls(self) -> int:
        """Executed calls. A refusal is the boundary working, not a tool that ran."""
        return sum(1 for e in self._events
                   if e.kind == "tool_result" and e.payload["status"] == "OK")

    @property
    def model_turns(self) -> int:
        """Responses the provider boundary recorded. Zero when no model ran."""
        return sum(1 for e in self._events if e.kind == "model_responded")

    def watch(self, tools: Tools) -> Tools:
        return _Watched(tools, self)


class _Watched:
    """The tool boundary as the investigator receives it: every crossing recorded."""

    def __init__(self, inner: Tools, recorder: Recorder) -> None:
        self._inner, self._recorder = inner, recorder

    def advertised(self) -> list[dict[str, object]]:
        """What the loop shows the model — the inner layer's schemas, untouched."""
        return self._inner.advertised()

    def execute(self, call: ToolCall) -> ToolResult:
        self._recorder.event("tool_call", {"call_id": call.call_id, "name": call.name,
                                           "arguments": call.arguments})
        result = self._inner.execute(call)
        self._recorder.event("tool_result", {"call_id": result.call_id, "name": result.name,
                                             "status": result.status, "content": result.content})
        return result


def run_incident(label: str, context: IncidentContext, investigator: Investigator,
                 tools: Tools, validator: Validator, *,
                 configuration: dict[str, object], recorder: Recorder | None = None) -> RunRecord:
    """Investigate, validate if a repair was proposed, and return the record — for every way
    a run can end. A submission carries its decision. A run the loop ended carries the loop's
    classification verbatim. Anything else that escapes is our defect: an infrastructure
    failure, with its traceback on stderr, never a lost run. In every case the trace so far
    is the evidence and the counters come from it. Only a REPAIR reaches the validator: the
    contract says so, and this is where it is enforced on the way through."""
    started = time.monotonic()
    recorder = recorder or Recorder()   # a provider records at its boundary into the same one
    recorder.event("incident_received", {"incident_id": context.incident_id})
    decision = authorization = validation = None
    try:
        decision = investigator.investigate(context, recorder.watch(tools))
        # the loop refuses a citation the model never received; an investigator that reaches
        # here with one — a script, or a defect — is ours, and no record carries the claim
        dangling = unresolved_citations(decision, recorder.trace)
        if dangling:
            raise RuntimeError("the decision cites evidence this run never minted: "
                               f"{', '.join(dangling)}")
        recorder.event("decision_submitted", {"disposition": decision.disposition.value})
        if decision.disposition is Disposition.REPAIR:
            # two facts about the one proposal, each its own authority's, neither gating
            # the other: the runtime's — are the targets permitted — and the validator's —
            # does it work. The validator is handed the incident without its permitted
            # paths: permission is never its question. The record carries both; the
            # authorization's trace form waits on the trace contract (D-1).
            authorization = authorize(context, decision)
            validation = validator.validate(replace(context, permitted_write_paths=()),
                                            decision)
            # the legacy placeholder is loadable from old records and never produced: a
            # validator that returns it has failed to say whether it checked anything
            if validation.state == "UNCHECKED":
                raise RuntimeError("the validator returned a legacy unchecked result — neither "
                                   "a verdict nor NOT_CHECKABLE; the runtime never records one")
            recorder.event("validation_completed", {"accepted": validation.accepted})
        termination, detail = "submitted", "the investigator committed to a disposition"
    except Terminated as ended:
        decision = authorization = validation = None
        termination, detail = ended.termination, ended.detail
    except Exception as defect:  # ours, not the model's: classified and shown, never hidden
        traceback.print_exc()
        decision = authorization = validation = None
        termination, detail = "infrastructure_failure", f"{type(defect).__name__}: {defect}"
    return strict(RunRecord(
        label=label, context=context, trace=recorder.trace, termination=termination,
        detail=detail, decision=decision, validation=validation, authorization=authorization,
        tool_calls=recorder.tool_calls,
        # Turns are counted from the model events the provider boundary recorded — zero when
        # no model ran. Cost stays 0.0: only local endpoints run here, and a paid provider
        # waits for the receipt and the ledger (plan D-15, D-12).
        model_turns=recorder.model_turns, api_cost_usd=0.0,
        latency_ms=int((time.monotonic() - started) * 1000),
        configuration=dict(configuration), provenance=provenance("runtime")))
