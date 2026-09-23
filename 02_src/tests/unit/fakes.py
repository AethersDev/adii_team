"""Test-only deterministic collaborators for investigator unit tests."""

import json

from adii.contracts import Disposition, InvestigationDecision, ToolCall, ToolResult
from adii.investigator.loop import DECISION_PREFIX

# How a scripted test ends a run now that there is no stop without a decision (trace
# contract row 5): an ESCALATE, which needs no observation, as the loop parses it.
END_SUMMARY = "The script ends here."
END = DECISION_PREFIX + json.dumps({"disposition": "ESCALATE", "root_cause_id": None,
                                    "root_cause_summary": END_SUMMARY})
ENDED = InvestigationDecision(Disposition.ESCALATE, None, END_SUMMARY)


class FakeToolExecutor:
    """Classify and execute one minimal fake tool without external access."""

    def __init__(self, *, marker: str | None = None) -> None:
        self.marker = marker
        self.calls: list[ToolCall] = []
        self.results: list[ToolResult] = []

    def execute(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)

        if call.name != "fake_tool":
            status = "DENIED"
            content: dict[str, object] = {"error": "unknown tool"}
        elif call.arguments.get("fail") is True:
            status = "ERROR"
            content = {"error": "controlled fake failure"}
        elif not isinstance(call.arguments.get("value"), str):
            status = "REJECTED"
            content = {"error": "value must be a string"}
        else:
            status = "OK"
            content = {"value": call.arguments["value"]}
            if self.marker is not None:
                content["marker"] = self.marker

        result = ToolResult(
            call_id=call.call_id,
            name=call.name,
            status=status,
            content=content,
        )
        self.results.append(result)
        return result


class StateAwareFakeProvider:
    """Choose one preformatted second action from accumulated tool results."""

    _INITIAL_PROBE = '<TOOL_CALL>{"name":"fake_tool","arguments":{"value":"probe"}}'

    def __init__(
        self,
        *,
        watch_marker: str,
        response_if_matched: str,
        response_if_unmatched: str,
    ) -> None:
        self.watch_marker = watch_marker
        self.response_if_matched = response_if_matched
        self.response_if_unmatched = response_if_unmatched
        self._turn = 0

    def respond(
        self,
        *,
        observation: ToolResult | None = None,
        observations: tuple[ToolResult, ...] = (),
    ) -> str:
        if self._turn == 0:
            response = self._INITIAL_PROBE
        elif self._turn == 1:
            marker = observations[-1].content.get("marker")
            response = (
                self.response_if_matched
                if marker == self.watch_marker
                else self.response_if_unmatched
            )
        else:
            response = END

        self._turn += 1
        return response


class RaisingProvider:
    """Return optional responses, then fail deterministically."""

    def __init__(self, *responses: str, error: Exception | None = None) -> None:
        self._responses = responses
        self._error = (
            error if error is not None else RuntimeError("deterministic provider failure")
        )
        self._cursor = 0
        self._received_observations: list[ToolResult | None] = []
        self._received_context: list[tuple[ToolResult, ...]] = []

    @property
    def received_observations(self) -> tuple[ToolResult | None, ...]:
        return tuple(self._received_observations)

    @property
    def received_context(self) -> tuple[tuple[ToolResult, ...], ...]:
        return tuple(self._received_context)

    def respond(
        self,
        *,
        observation: ToolResult | None = None,
        observations: tuple[ToolResult, ...] = (),
    ) -> str:
        self._received_observations.append(observation)
        self._received_context.append(tuple(observations))
        if self._cursor < len(self._responses):
            response = self._responses[self._cursor]
            self._cursor += 1
            return response
        raise self._error


class NonStringProvider:
    """Return one deterministic non-string value."""

    def __init__(self, value: object) -> None:
        self.value = value

    def respond(
        self,
        *,
        observation: ToolResult | None = None,
        observations: tuple[ToolResult, ...] = (),
    ) -> object:
        return self.value


class RaisingToolExecutor:
    """Record a call, then fail deterministically."""

    def __init__(self) -> None:
        self.calls: list[ToolCall] = []

    def execute(self, call: ToolCall) -> ToolResult:
        self.calls.append(call)
        raise RuntimeError("deterministic executor failure")


class NonToolResultExecutor:
    """Return a deterministic value that violates the executor boundary."""

    def __init__(self, value: object) -> None:
        self.value = value
        self.calls: list[ToolCall] = []

    def execute(self, call: ToolCall) -> object:
        self.calls.append(call)
        return self.value
