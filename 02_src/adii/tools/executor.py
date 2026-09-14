"""The door. A `ToolCall` comes in, a `ToolResult` goes out, and nothing else crosses.

The executor is a registry of tools plus the one function that dispatches to them. It is
where the four statuses are decided, so it is where they are kept apart:

    DENIED     unknown tool, spent budget, or a handler that refused
    REJECTED   arguments that fail the advertised schema, or a handler that sent them back
    ERROR      a handler raised something it did not mean to — our defect
    OK         the handler ran, and its observation carries an evidence id

Every `OK` observation is stamped with an evidence id derived from the tool, its
arguments, and what it returned, so a decision can cite something that actually happened,
and the same observation made twice gets the same id.

The trace is not kept here. The loop that calls `execute` records the call and the result;
counters come from that trace, never from this object (CONFORMANCE D2).
"""
from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping

from ..contracts import ToolCall, ToolResult
from .errors import Denied, Rejected
from .schemas import ToolSpec, validate_arguments

Handler = Callable[..., Mapping[str, object]]

EVIDENCE_PREFIX = "ev-"


def evidence_id(name: str, arguments: Mapping[str, object], content: Mapping[str, object]) -> str:
    """Stable: the same tool, arguments, and observation always produce the same id."""
    digest = hashlib.sha256(canonical_json(
        {"name": name, "arguments": arguments, "content": content}).encode("utf-8"))
    return EVIDENCE_PREFIX + digest.hexdigest()[:16]


def canonical_json(value: object) -> str:
    """Strict JSON (CONFORMANCE D3): no NaN, no Infinity, keys sorted. Raises if the value
    cannot be represented — a tool that returns something else has a bug."""
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))


class ToolExecutor:
    """Registry and dispatcher. One per investigation, so the call budget is per run."""

    def __init__(self, *, max_calls: int | None = None) -> None:
        # CONFORMANCE A6/A7: a public API enforces its own bounds. A negative, boolean, or
        # non-finite budget would silently disable the limit while looking like one.
        if max_calls is not None:
            if isinstance(max_calls, bool) or not isinstance(max_calls, int):
                raise ValueError(f"max_calls must be an int or None, got {max_calls!r}")
            if max_calls < 0 or not math.isfinite(max_calls):
                raise ValueError(f"max_calls must be non-negative, got {max_calls!r}")
        self.max_calls = max_calls
        self.calls_dispatched = 0
        self._tools: dict[str, tuple[ToolSpec, Handler]] = {}

    def register(self, spec: ToolSpec, handler: Handler) -> None:
        if spec.name in self._tools:
            raise ValueError(f"tool {spec.name!r} is already registered")
        self._tools[spec.name] = (spec, handler)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def advertised(self) -> list[dict[str, object]]:
        """What the loop shows the model. Exactly the schemas that `execute` enforces."""
        return [spec.to_json_schema() for spec, _ in self._tools.values()]

    def execute(self, call: ToolCall) -> ToolResult:
        tool = self._tools.get(call.name)
        if tool is None:
            return self._result(call, "DENIED", {
                "error": f"unknown tool {call.name!r}",
                "known_tools": list(self._tools)})

        if self.max_calls is not None and self.calls_dispatched >= self.max_calls:
            return self._result(call, "DENIED", {
                "error": f"tool-call budget of {self.max_calls} is spent",
                "calls_dispatched": self.calls_dispatched})

        spec, handler = tool
        problems = validate_arguments(spec, call.arguments)
        if problems:
            return self._result(call, "REJECTED", {
                "error": "invalid arguments: " + "; ".join(problems),
                "problems": problems})

        self.calls_dispatched += 1
        try:
            observation = handler(**call.arguments)
        except Denied as refusal:
            return self._result(call, "DENIED", {"error": str(refusal)})
        except Rejected as pushback:
            return self._result(call, "REJECTED", {"error": str(pushback)})
        except Exception as defect:  # noqa: BLE001 — anything else is our bug, filed as such
            return self._result(call, "ERROR", {
                "error": f"{type(defect).__name__}: {defect}", "tool": call.name})

        if not isinstance(observation, Mapping):
            return self._result(call, "ERROR", {
                "error": f"tool {call.name!r} returned {type(observation).__name__}, "
                         "not an object", "tool": call.name})
        content = dict(observation)
        try:
            content["evidence_id"] = evidence_id(call.name, call.arguments, content)
        except (TypeError, ValueError) as defect:
            return self._result(call, "ERROR", {
                "error": f"tool {call.name!r} returned content that is not strict JSON: "
                         f"{defect}", "tool": call.name})
        return self._result(call, "OK", content)

    @staticmethod
    def _result(call: ToolCall, status: str, content: dict[str, object]) -> ToolResult:
        return ToolResult(call_id=call.call_id, name=call.name, status=status, content=content)
