"""The v0 contracts. Nine names — one enum and eight frozen dataclasses — no logic.

WHY THESE SHAPES AND NOT OTHERS. Not a free design exercise. A working implementation of
ADII was built, evaluated, and audited before this one, and these are the shapes that
survived it: `InvestigationDecision` is a submission a judge can score without asking the
agent anything further, and `InvestigationRun` carries what an archive needs to be
replayable months later. Each invariant below is here because its absence produced a real
defect -- docs/inherited/CONFORMANCE.md names them.

We own these now. Changing one is a cross-boundary human decision, not a refactor.

WHAT LIVES HERE: shapes and the invariants that make a shape meaningful.
WHAT DOES NOT: model calls, SQL, scoring, file IO, provider SDKs. Nothing in this module
imports anything outside the standard library, so every component can depend on it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Disposition(StrEnum):
    """The only three answers ADII may give.

    REPAIR    — a specific fault exists and the evidence justifies a specific fix.
    NO_REPAIR — the pipeline is sound; the metric moved because the business moved.
    ESCALATE  — the evidence cannot justify either call. Say what is missing and why.
    """

    REPAIR = "REPAIR"
    NO_REPAIR = "NO_REPAIR"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class IncidentContext:
    """Everything the investigator is told. Notably absent: any path into the filesystem.

    The investigator sees the world only through tools. If it could read files
    directly it could read the answer key, and the evaluation would mean nothing.
    """

    incident_id: str
    alert: str
    as_of: str
    permitted_write_paths: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.incident_id.strip():
            raise ValueError("incident_id must not be empty")
        if not self.alert.strip():
            raise ValueError("alert must not be empty")


@dataclass(frozen=True)
class ToolCall:
    """INVESTIGATOR  ──▶  CONTROLLED TOOLS"""

    call_id: str
    name: str
    arguments: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.call_id.strip() or not self.name.strip():
            raise ValueError("call_id and name must not be empty")


@dataclass(frozen=True)
class ToolResult:
    """CONTROLLED TOOLS  ──▶  INVESTIGATOR

    `status` is part of the contract because the investigator has to be able to tell a
    refusal from an answer:

      OK        the tool ran and this is what it saw
      DENIED    the tool refused (unknown tool, budget spent, outside permissions)
      REJECTED  the arguments were wrong — the model's mistake, and it may retry
      ERROR     the tool broke; that is our defect, not the model's
    """

    STATUSES = ("OK", "DENIED", "REJECTED", "ERROR")

    call_id: str
    name: str
    status: str
    content: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in self.STATUSES:
            raise ValueError(f"status must be one of {self.STATUSES}, got {self.status!r}")

    @property
    def ok(self) -> bool:
        return self.status == "OK"


@dataclass(frozen=True)
class TraceEvent:
    """EVERY COMPONENT  ──▶  TELEMETRY

    One thing that happened, in order. The trace is the run's evidence: if a behaviour is
    not in the trace, telemetry cannot show it and nobody can debug it.
    """

    sequence: int
    kind: str
    payload: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        if not self.kind.strip():
            raise ValueError("kind must not be empty")


@dataclass(frozen=True)
class InvestigationDecision:
    """INVESTIGATOR  ──▶  VALIDATION / EVALUATION

    The submission. Its three invariants are enforced HERE, at the point of
    construction, so a malformed decision cannot travel to the authority that judges it.
    """

    disposition: Disposition
    root_cause_id: str | None
    root_cause_summary: str
    repair_id: str | None = None
    patch: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.root_cause_summary.strip():
            raise ValueError("every decision must explain itself in root_cause_summary")
        if self.disposition is Disposition.REPAIR:
            if not self.repair_id or not self.patch:
                raise ValueError("a REPAIR decision must carry a repair_id and a patch")
        elif self.repair_id or self.patch:
            raise ValueError("only a REPAIR decision may carry a repair_id or a patch")


# The one reason a verdict can carry today: the validator has no world to rebuild for the
# incident. A closed set — a code outside it is an invalid result, refused at construction.
REASON_CODES = ("no_rebuildable_world",)


@dataclass(frozen=True)
class ValidationResult:
    """INDEPENDENT VALIDATION  ──▶  TELEMETRY

    ACCEPT/REJECT of a candidate repair, decided by rebuilding from the frozen inputs — or
    NOT_CHECKABLE, when there was no world to rebuild, said in structure by `reason_code`.

    THE AUTHORITY BOUNDARY. The investigator has its own rehearsal tool and it will
    happily tell itself the patch works. That is a hypothesis, not a verdict. Only this
    result decides, and the investigator never sees how it was reached.

    The state space is closed (decided 22 September 2026, m7_validation_integration.md):

        ACCEPT           accepted=True   reason_code=None   checks_run any
        REJECT           accepted=False  reason_code=None   checks_run non-empty
        NOT_CHECKABLE    accepted=False  reason_code set    checks_run=()
        UNCHECKED        accepted=False  reason_code=None   checks_run=()   legacy: loadable
                         from archived records, never produced by the runtime

    Any other combination is refused here. `state` is the one derivation every reader uses.
    """

    accepted: bool
    report: str
    checks_run: tuple[str, ...] = ()
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if not self.report.strip():
            raise ValueError("a validation result must explain itself in report")
        if self.reason_code is not None:
            if self.reason_code not in REASON_CODES:
                raise ValueError(f"unknown reason_code {self.reason_code!r}; the closed set is "
                                 f"{REASON_CODES}")
            if self.accepted:
                raise ValueError("a verdict that could not be established cannot be accepted")
            if self.checks_run:
                raise ValueError("a verdict that could not be established names no checks")

    @property
    def state(self) -> str:
        """ACCEPT, REJECT, NOT_CHECKABLE, or the legacy UNCHECKED — derived once, here."""
        if self.accepted:
            return "ACCEPT"
        if self.reason_code is not None:
            return "NOT_CHECKABLE"
        return "REJECT" if self.checks_run else "UNCHECKED"


# The one reason a patch can be denied today: it touches a path the incident did not
# permit. A closed set — a code outside it is an invalid fact, refused at construction.
AUTHORIZATION_REASONS = ("target_not_permitted",)


@dataclass(frozen=True)
class RepairAuthorization:
    """RUNTIME  ──▶  TELEMETRY

    Whether every path a REPAIR's patch touches is one the incident permitted. The runtime's
    own fact, established for every REPAIR beside — never instead of, never gated by — the
    validator's verdict (m7_validation_integration.md, row 4, decided 22 September 2026).
    It says nothing about whether the patch works; the validator says nothing about whether
    it was allowed. Admission is derived from both and stored nowhere.

        AUTHORIZED   authorized=True    denied_paths=()          reason_code=None
        DENIED       authorized=False   denied_paths non-empty   reason_code set

    A patch is authorized whole or not at all: one target outside the permitted paths denies
    the patch entire, and `denied_paths` names every such target. `checked_paths` is every
    target the patch named, so the fact is auditable without the decision beside it.
    """

    authorized: bool
    checked_paths: tuple[str, ...]
    denied_paths: tuple[str, ...] = ()
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if not self.checked_paths:
            raise ValueError("an authorization names the paths it checked")
        if set(self.denied_paths) - set(self.checked_paths):
            raise ValueError("a denied path is one of the paths that were checked")
        if self.authorized != (not self.denied_paths):
            raise ValueError("authorized means no path was denied, and nothing else")
        if self.reason_code is None:
            if not self.authorized:
                raise ValueError("a denial carries its reason_code")
        elif self.reason_code not in AUTHORIZATION_REASONS:
            raise ValueError(f"unknown reason_code {self.reason_code!r}; the closed set is "
                             f"{AUTHORIZATION_REASONS}")
        elif self.authorized:
            raise ValueError("an authorization carries no reason_code")


@dataclass(frozen=True)
class InvestigationRun:
    """The whole public run: what was asked, what was decided, what it cost.

    Note what the agent does NOT get to report:
    `tool_calls` is counted from the harness-owned trace, so an investigator cannot
    flatter its own efficiency.
    """

    incident_id: str
    decision: InvestigationDecision
    trace: tuple[TraceEvent, ...] = ()
    validation: ValidationResult | None = None
    tool_calls: int = 0
    model_turns: int = 0
    api_cost_usd: float = 0.0
    latency_ms: int = 0

    def __post_init__(self) -> None:
        for name in ("tool_calls", "model_turns", "latency_ms"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.api_cost_usd < 0:
            raise ValueError("api_cost_usd must be non-negative")
        if self.decision.disposition is Disposition.REPAIR and self.validation is None:
            raise ValueError("a REPAIR run must carry an independent ValidationResult")
        if self.decision.disposition is not Disposition.REPAIR and self.validation is not None:
            raise ValueError("only a REPAIR run has a repair to validate")
