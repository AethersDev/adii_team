"""Test-only deterministic collaborators for investigator unit tests."""

from adii.contracts import ToolCall, ToolResult
from adii.investigator.loop import STOP_SIGNAL


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
            response = STOP_SIGNAL

        self._turn += 1
        return response
