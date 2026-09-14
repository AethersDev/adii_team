"""Deterministic model substitute for investigator tests."""

from collections.abc import Sequence

from ..contracts import ToolResult


class ScriptExhaustedError(RuntimeError):
    """Raised when a scripted provider has no response left to return."""


class ScriptedProvider:
    """Return pre-scripted string responses in order, one per call."""

    def __init__(self, responses: Sequence[str]) -> None:
        self._responses = tuple(responses)
        if not self._responses:
            raise ValueError("scripted provider requires at least one response")
        self._cursor = 0
        self._received_observations: list[ToolResult | None] = []
        self._received_context: list[tuple[ToolResult, ...]] = []

    @property
    def received_observations(self) -> tuple[ToolResult | None, ...]:
        """Observations supplied to each provider invocation, in call order."""
        return tuple(self._received_observations)

    @property
    def received_context(self) -> tuple[tuple[ToolResult, ...], ...]:
        """Accumulated observation tuples supplied to each invocation."""
        return tuple(self._received_context)

    def respond(
        self,
        *,
        observation: ToolResult | None = None,
        observations: tuple[ToolResult, ...] = (),
    ) -> str:
        """Return the next response, or fail clearly when the script is exhausted."""
        self._received_observations.append(observation)
        self._received_context.append(tuple(observations))
        if self._cursor >= len(self._responses):
            raise ScriptExhaustedError("scripted provider has no responses remaining")

        response = self._responses[self._cursor]
        self._cursor += 1
        return response
