"""Task-A-local accumulated investigation knowledge."""

from dataclasses import dataclass

from ..contracts import ToolResult


@dataclass(frozen=True)
class InvestigationState:
    """Tool observations accumulated across model turns."""

    observations: tuple[ToolResult, ...] = ()
