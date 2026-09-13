"""Scripted stand-ins for the three components the runtime orchestrates.

A script is not an agent: it makes its calls in order and commits its decision without
reading a single result. That is the point. With these three, the runtime's own record is
the only place the run exists, which is what "counters come from the trace" has to mean.
"""
from __future__ import annotations

from ..contracts import (
    IncidentContext,
    InvestigationDecision,
    InvestigationRun,
    ToolCall,
    ToolResult,
    ValidationResult,
)
from .run import Tools


class ScriptedTools:
    """Answers each call from the script, by call id. A call the script does not answer is
    a harness mistake and raises: fabricating a refusal would put a refusal on the record
    that no boundary ever made."""

    def __init__(self, results: dict[str, ToolResult]) -> None:
        self._results = results

    def execute(self, call: ToolCall) -> ToolResult:
        if call.call_id not in self._results:
            raise ValueError(f"the script has no result for call {call.call_id!r} ({call.name})")
        return self._results[call.call_id]


class ScriptedInvestigator:
    def __init__(self, calls: tuple[ToolCall, ...], decision: InvestigationDecision) -> None:
        self._calls, self._decision = calls, decision

    def investigate(self, context: IncidentContext, tools: Tools) -> InvestigationDecision:
        for call in self._calls:
            tools.execute(call)
        return self._decision


class ScriptedValidator:
    def __init__(self, result: ValidationResult | None) -> None:
        self._result = result

    def validate(self, context: IncidentContext,
                 decision: InvestigationDecision) -> ValidationResult:
        if self._result is None:
            raise ValueError("the validator was invoked, but the script proposed no repair")
        return self._result


def scripted(run: InvestigationRun,
             ) -> tuple[ScriptedInvestigator, ScriptedTools, ScriptedValidator]:
    """The three components, scripted from a recorded run. Today that run is the
    walkthrough's. The command line takes the investigator and the validator from here and
    the tools from `adii.tools`; tests take all three when the trace must reproduce the
    recorded one exactly."""
    calls = tuple(ToolCall(call_id=e.payload["call_id"], name=e.payload["name"],
                           arguments=e.payload["arguments"])
                  for e in run.trace if e.kind == "tool_call")
    results = {e.payload["call_id"]: ToolResult(call_id=e.payload["call_id"],
                                                name=e.payload["name"],
                                                status=e.payload["status"],
                                                content=e.payload["content"])
               for e in run.trace if e.kind == "tool_result"}
    return ScriptedInvestigator(calls, run.decision), ScriptedTools(results), \
        ScriptedValidator(run.validation)
