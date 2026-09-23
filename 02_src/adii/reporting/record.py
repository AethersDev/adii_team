"""The run record — one strict, versioned document per run.

Holds what A, B and C produced without depending on how they produced it: the incident the
investigator was handed, every trace event in order, how the run ended, the decision if there
was one, the verdict if there was one, what it cost, the configuration it ran under, and
where the record came from. The archive stores this shape and the inspector renders it, and
nothing else. When the shape changes, SCHEMA changes with it and old files keep loading
under the version they declare.

Two refusals, both at the boundary: a document whose schema this reader does not know is
never guessed at, and a value that is not JSON — NaN or Infinity — never reaches a sink,
because an archive no conforming parser can read back is not an archive.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from ..contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    InvestigationRun,
    RepairAuthorization,
    TraceEvent,
    ValidationResult,
)

SCHEMA = "adii.run_record/v3"
# v2, written 23 Sep 2026 before decision F2: no validation rebuilt_series. Read as it
# declares itself, that field empty; a v3 record without it is malformed.
V2 = "adii.run_record/v2"
# v1, written before 22 Sep: no evidence_refs, no validation reason_code, no authorization.
# Read as it declares itself, those fields absent; a v2 record without one is malformed.
V1 = "adii.run_record/v1"
REPO = Path(__file__).resolve().parents[3]
ARCHIVE = REPO / "01_data" / "runs"
# A label names the run's directory in the archive and its URL in the inspector, so it is
# exactly one path segment: nothing that could leave the archive, nest inside it, or fail
# to survive a URL.
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _check_label(label: str) -> None:
    if not LABEL.fullmatch(label):
        raise ValueError("label must be one path segment: letters, digits, '.', '_' and '-', "
                         f"starting with a letter or digit; got {label!r}")

# How a run ended: a closed set, the loop's own classification, preserved and never
# reinterpreted. `detail` is free text beside it — never instead of it, or the archive fills
# with "timeout", "model timeout" and "provider timeout" and the report has to reinterpret
# the one thing the record existed to preserve. Only "submitted" carries a decision.
TERMINATIONS = ("submitted", "model_failure", "bound_hit", "infrastructure_failure")


@dataclass(frozen=True)
class RunRecord:
    label: str
    context: IncidentContext
    trace: tuple[TraceEvent, ...]
    termination: str
    detail: str
    decision: InvestigationDecision | None
    validation: ValidationResult | None
    tool_calls: int
    model_turns: int
    api_cost_usd: float
    latency_ms: int
    configuration: dict[str, object]
    provenance: dict[str, str | None]
    # the runtime's fact about a REPAIR's targets (m7 row 4); None on records written
    # before 22 September 2026, and on any run that proposed no repair
    authorization: RepairAuthorization | None = None

    def __post_init__(self) -> None:
        _check_label(self.label)
        if self.termination not in TERMINATIONS:
            raise ValueError(
                f"termination must be one of {TERMINATIONS}, got {self.termination!r}")
        if (self.termination == "submitted") != (self.decision is not None):
            raise ValueError("a submitted run carries a decision, and only a submitted run does")
        if self.validation is not None and (
                self.decision is None or self.decision.disposition is not Disposition.REPAIR):
            raise ValueError("only a REPAIR decision has a repair to validate")
        if (self.termination == "submitted" and self.validation is None
                and self.decision.disposition is Disposition.REPAIR):
            raise ValueError("a submitted REPAIR carries the validator's verdict")
        if self.authorization is not None and (
                self.decision is None or self.decision.disposition is not Disposition.REPAIR):
            raise ValueError("only a REPAIR decision has targets to authorize")
        if self.decision is not None:
            dangling = unresolved_citations(self.decision, self.trace)
            if dangling:
                raise ValueError("a decision cites evidence its trace never minted: "
                                 f"{', '.join(dangling)}")
        for name in ("tool_calls", "model_turns", "latency_ms"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")
        if not math.isfinite(self.api_cost_usd) or self.api_cost_usd < 0:
            raise ValueError(
                f"api_cost_usd must be finite and non-negative, got {self.api_cost_usd!r}")

    @property
    def admissible(self) -> bool:
        """Derived here, stored nowhere (m7 row 4): the runtime's fact and the validator's,
        both established and both in the repair's favour. A denial, a rejection, a verdict
        that was not established, or a missing fact is not admissible. Nothing executes
        either way."""
        return (self.authorization is not None and self.authorization.authorized
                and self.validation is not None and self.validation.state == "ACCEPT")

    @classmethod
    def from_run(cls, label: str, context: IncidentContext, run: InvestigationRun, *,
                 configuration: dict[str, object], origin: str,
                 authorization: RepairAuthorization | None = None) -> RunRecord:
        """A submitted run assembled outside the runtime — the walkthrough's, which
        establishes the runtime's authorization fact with the runtime's own function."""
        return cls(
            label=label, context=context, trace=run.trace,
            termination="submitted", detail="the investigator committed to a disposition",
            decision=run.decision, validation=run.validation,
            tool_calls=run.tool_calls, model_turns=run.model_turns,
            api_cost_usd=run.api_cost_usd, latency_ms=run.latency_ms,
            configuration=dict(configuration), provenance=provenance(origin),
            authorization=authorization)

    def to_json(self) -> str:
        """Strict RFC 8259. Raises ValueError on NaN or Infinity anywhere in the record,
        before anything reaches a sink."""
        context, decision, validation = self.context, self.decision, self.validation
        authorization = self.authorization
        doc = {
            "schema": SCHEMA,
            "label": self.label,
            "termination": self.termination,
            "detail": self.detail,
            "context": {"incident_id": context.incident_id, "alert": context.alert,
                        "as_of": context.as_of,
                        "permitted_write_paths": list(context.permitted_write_paths)},
            "trace": [{"sequence": e.sequence, "kind": e.kind, "payload": e.payload}
                      for e in self.trace],
            "decision": None if decision is None else {
                "disposition": decision.disposition.value,
                "root_cause_id": decision.root_cause_id,
                "root_cause_summary": decision.root_cause_summary,
                "repair_id": decision.repair_id, "patch": decision.patch,
                "evidence_refs": list(decision.evidence_refs)},
            "validation": None if validation is None else {
                "accepted": validation.accepted, "report": validation.report,
                "checks_run": list(validation.checks_run),
                "reason_code": validation.reason_code,
                "rebuilt_series": [list(row) for row in validation.rebuilt_series]},
            "authorization": None if authorization is None else {
                "authorized": authorization.authorized,
                "checked_paths": list(authorization.checked_paths),
                "denied_paths": list(authorization.denied_paths),
                "reason_code": authorization.reason_code},
            "counters": {"tool_calls": self.tool_calls, "model_turns": self.model_turns,
                         "api_cost_usd": self.api_cost_usd, "latency_ms": self.latency_ms},
            "configuration": self.configuration,
            "provenance": self.provenance,
        }
        return json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def unresolved_citations(decision: InvestigationDecision,
                         trace: tuple[TraceEvent, ...]) -> tuple[str, ...]:
    """The cited ids this trace never minted. An evidence id exists only on a successful tool
    result, minted by the tool layer (inherited D2); a decision may reference one, never
    invent one. Empty means every citation resolves — or there are none."""
    minted = set()
    for event in trace:        # a payload of any other shape minted nothing
        content = event.payload.get("content")
        if (event.kind == "tool_result" and event.payload.get("status") == "OK"
                and isinstance(content, dict)):
            minted.add(content.get("evidence_id"))
    return tuple(ref for ref in decision.evidence_refs if ref not in minted)


def _not_json(constant: str) -> None:
    raise ValueError(f"{constant} is not JSON")


def _patch(patch: object) -> dict[str, str]:
    """The contract's `dict[str, str]`: each path to its new contents. Anything else is a
    record no renderer should meet."""
    if not isinstance(patch, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in patch.items()):
        raise TypeError("patch must map each path to its new contents, as text")
    return patch


def from_json(text: str) -> RunRecord:
    """Parse one record. Refuses any schema but SCHEMA — a reader that guesses at a shape
    it does not know is how an archive drifts from its source without anyone noticing."""
    doc = json.loads(text, parse_constant=_not_json)
    schema = doc.get("schema") if isinstance(doc, dict) else None
    if schema not in (SCHEMA, V2, V1):
        raise ValueError(f"unknown record schema {schema!r}: this reader understands {SCHEMA}, "
                         f"{V2} and {V1}")
    v1, v3 = schema == V1, schema == SCHEMA
    try:
        c, d, v, n = doc["context"], doc["decision"], doc["validation"], doc["counters"]
        a = doc.get("authorization") if v1 else doc["authorization"]
        return RunRecord(
            label=doc["label"],
            context=IncidentContext(
                incident_id=c["incident_id"], alert=c["alert"], as_of=c["as_of"],
                permitted_write_paths=tuple(c["permitted_write_paths"])),
            trace=tuple(TraceEvent(sequence=e["sequence"], kind=e["kind"], payload=e["payload"])
                        for e in doc["trace"]),
            termination=doc["termination"], detail=doc["detail"],
            decision=None if d is None else InvestigationDecision(
                disposition=Disposition(d["disposition"]), root_cause_id=d["root_cause_id"],
                root_cause_summary=d["root_cause_summary"], repair_id=d["repair_id"],
                patch=_patch(d["patch"]),
                evidence_refs=tuple(d.get("evidence_refs", ()) if v1 else d["evidence_refs"])),
            validation=None if v is None else ValidationResult(
                accepted=v["accepted"], report=v["report"], checks_run=tuple(v["checks_run"]),
                reason_code=v.get("reason_code") if v1 else v["reason_code"],
                rebuilt_series=tuple(tuple(row) for row in v["rebuilt_series"]) if v3 else ()),
            authorization=None if a is None else RepairAuthorization(
                authorized=a["authorized"], checked_paths=tuple(a["checked_paths"]),
                denied_paths=tuple(a["denied_paths"]), reason_code=a["reason_code"]),
            tool_calls=n["tool_calls"], model_turns=n["model_turns"],
            api_cost_usd=n["api_cost_usd"], latency_ms=n["latency_ms"],
            configuration=doc["configuration"], provenance=doc["provenance"])
    except KeyError as missing:
        raise ValueError(f"record is missing {missing}") from missing
    except TypeError as shape:      # a field of the wrong shape — a trace that is a string, say
        raise ValueError(f"record is malformed: {shape}") from shape


def write_record(record: RunRecord, root: Path) -> Path:
    """`root/<label>/record.json`, never overwritten: a label names one run forever. The
    record is serialised — and so validated — before the directory is reserved."""
    path = root / record.label / "record.json"
    if path.exists():
        raise FileExistsError(f"{path} exists; a label names one run, choose another")
    text = record.to_json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def reserve(root: Path, label: str) -> Path:
    """Claim `root/<label>` before the run starts, so a taken label is refused before anything
    is spent. Call it only after every precondition that needs no I/O has passed: a run that
    is refused for any other reason must leave the label reusable. Raises FileExistsError
    when the label is taken."""
    _check_label(label)
    path = root / label
    try:
        path.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise FileExistsError(f"{path} exists; a label names one run, choose another") from None
    return path


def strict(record: RunRecord) -> RunRecord:
    """The record if it is strict JSON; otherwise the same run as an infrastructure failure
    that names the poison, keeping every event whose payload is strict JSON on its own. A
    payload that is not JSON is our defect, and the archive shows the run that produced it
    rather than losing it. Nothing but the trace can carry a poison in, so if the result
    still does not serialise the failure is terminal."""
    try:
        record.to_json()
    except (TypeError, ValueError) as poison:
        kept = tuple(e for e in record.trace if _is_strict(e.payload))
        return replace(record, trace=kept, decision=None, validation=None, authorization=None,
                       termination="infrastructure_failure",
                       detail=f"record is not strict JSON: {poison}")
    return record


def _is_strict(payload: object) -> bool:
    try:
        json.dumps(payload, allow_nan=False)
    except (TypeError, ValueError):
        return False
    return True


def read_record(path: Path) -> RunRecord:
    return from_json(path.read_text(encoding="utf-8"))


def provenance(origin: str) -> dict[str, str | None]:
    """Where a record came from, captured at the moment the record is made: the source
    revision is read now, never cached for the life of a process."""
    return {"origin": origin,
            "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_revision": source_revision()}


def source_revision(root: Path = REPO) -> str | None:
    """The commit the working tree is at, read now rather than remembered, so a long-lived
    process cannot stamp every record with the revision it started at. None when there is
    no repository to read — from a ZIP, say."""
    git = root / ".git"
    head = git / "HEAD"
    if not head.is_file():
        return None
    ref = head.read_text(encoding="utf-8").strip()
    if not ref.startswith("ref: "):
        return ref                                     # detached HEAD holds the hash itself
    name = ref[5:]
    loose = git / name
    if loose.is_file():
        return loose.read_text(encoding="utf-8").strip()
    packed = git / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + name):
                return line.split(" ", 1)[0]
    return None
