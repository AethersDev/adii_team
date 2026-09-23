"""The independent authority: satisfies `runtime.run.Validator`.

CONFORMANCE C1. The investigator hands over a `REPAIR` decision and this is the only place
that decides whether it holds. It rebuilds the incident's world from frozen inputs with the
patch applied (`patching.apply_patch`), puts the rebuild through the incident's invariants
(`checks.check`), and returns `ACCEPT` only if every one agrees.

What it knows of an incident is one file beside it, `oracles/<incident_id>.json`, the
validator's own authority: the pipeline the world is derived by, and the invariants a valid
repaired world satisfies — never a patch, a repair id or a disposition. An incident with no
oracle has no world this validator can rebuild, and it says so (`UnknownIncident`) rather
than guessing. The frozen inputs are the incident's own: its world and its transform bundle,
the ones the investigator's tools were built over.

`validate()`'s signature is `(context, decision) -> ValidationResult`, and nothing here reads
`decision`'s prose or any rehearsal the investigator ran: only `decision.patch` reaches the
rebuild, which has no parameter a rehearsal claim could arrive through.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from adii.contracts import Disposition, IncidentContext, InvestigationDecision, ValidationResult
from adii.reporting.record import REPO
from adii.tools import ReadOnlyDatabase, load_transform_sources
from adii.tools.errors import Rejected
from adii.tools.walkthrough_world import build_script as walkthrough_world

from .checks import Invariant, changes_the_world, check
from .patching import PatchRejected, Step, apply_patch

ORACLES = Path(__file__).resolve().parent / "oracles"
MAX_SERIES_ROWS = 400
INCIDENTS = REPO / "01_data" / "incidents"
WALKTHROUGH = ("demo-learning-001", REPO / "01_data" / "walkthrough")   # its world is code
SCHEMA = "adii.validation_oracle/v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


class UnknownIncident(Exception):
    """This validator has no oracle for the incident, so no world to rebuild. Not a verdict:
    the runtime says NOT_CHECKABLE, in structure, and keeps the decision."""


def load_oracle(path: Path) -> tuple[tuple[Step, ...], tuple[Invariant, ...]]:
    """An oracle as the validator reads it: a closed shape, so nothing but a pipeline and
    invariants can be written in one — no patch, no repair id, no disposition."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or set(doc) != {"schema", "incident_id", "pipeline",
                                                 "invariants"} or doc["schema"] != SCHEMA:
        raise ValueError(f"{path.name} is not an {SCHEMA} document: schema, incident_id, "
                         "pipeline and invariants, and nothing else")
    if doc["incident_id"] != path.stem:
        raise ValueError(f"{path.name} is the oracle of {doc['incident_id']!r}")
    pipeline = []
    for step in doc["pipeline"]:
        if set(step) not in ({"table", "transform"}, {"table", "sql"}):
            raise ValueError(f"{path.name}: a pipeline step is a table and either the "
                             f"transform it is derived by or its own SQL; got {sorted(step)}")
        pipeline.append(Step(**step))
    invariants = [Invariant(**inv) for inv in doc["invariants"]]
    names = [inv.name for inv in invariants]
    if not invariants or len(set(names)) != len(names) or "rebuild" in names:
        raise ValueError(f"{path.name}: one or more invariants, each named once, and none "
                         "named rebuild — that is the rebuild's own check")
    return tuple(pipeline), tuple(invariants)


class Validator:
    """The object shape `run_incident()` calls. `oracles` and `incidents` say where the
    validator's authority and the incidents' frozen inputs are; tests point them elsewhere."""

    def __init__(self, oracles: Path = ORACLES, incidents: Path = INCIDENTS) -> None:
        self._oracles, self._incidents = oracles, incidents

    def frozen_inputs(self, incident_id: str) -> tuple[str, dict[str, str]]:
        """The incident's world build script and its transform bundle."""
        if incident_id == WALKTHROUGH[0]:
            return walkthrough_world(), load_transform_sources(WALKTHROUGH[1])
        folder = self._incidents / incident_id
        return (folder / "world.sql").read_text(encoding="utf-8"), load_transform_sources(folder)

    def validate(self, context: IncidentContext,
                 decision: InvestigationDecision) -> ValidationResult:
        path = self._oracles / f"{context.incident_id}.json"
        if not (_ID.fullmatch(context.incident_id) and path.is_file()):
            raise UnknownIncident(
                f"validation has no oracle for incident_id={context.incident_id!r}")
        pipeline, invariants = load_oracle(path)
        world, transforms = self.frozen_inputs(context.incident_id)
        frozen = ReadOnlyDatabase.in_memory(world)
        # the rebuild is the first check: a patch the world cannot apply is a rejection by the
        # check named `rebuild`, never the legacy "nothing checked" shape
        try:
            rebuilt = apply_patch(world, pipeline, transforms, decision.patch,
                                  world_ticks=frozen.build_ticks)
        except PatchRejected as problem:
            return ValidationResult(accepted=False, report=f"rebuild: patch rejected: {problem}",
                                    checks_run=("rebuild",))
        outcomes = [changes_the_world(tuple(step.table for step in pipeline), frozen, rebuilt),
                    *(check(invariant, frozen, rebuilt) for invariant in invariants)]
        accepted = all(outcome.passed for outcome in outcomes)
        report = "rebuild: the world rebuilt with the patch applied; " + "; ".join(
            f"{o.name}: {'holds' if o.passed else 'fails'} — {o.detail}" for o in outcomes)
        return ValidationResult(accepted=accepted, report=report,
                                checks_run=("rebuild", *(o.name for o in outcomes)),
                                rebuilt_series=self.alerted_series(context.incident_id, rebuilt))

    def alerted_series(self, incident_id: str, rebuilt: ReadOnlyDatabase) -> tuple:
        """The incident's declared alerted series, read from the rebuilt world with the
        query the runtime read the frozen one with; () when none is declared."""
        spec = self._incidents / incident_id / "alert_series.json"
        if incident_id == WALKTHROUGH[0] or not spec.is_file():
            return ()
        query = json.loads(spec.read_text(encoding="utf-8"))["query"]
        try:
            return rebuilt.query(query, max_rows=MAX_SERIES_ROWS).rows
        except Rejected:        # the patch reshaped what the query reads: no series to draw,
            return ()           # and the verdict — already decided by the checks — stands


def validate(context: IncidentContext, decision: InvestigationDecision) -> ValidationResult:
    """The default validator's verdict: the oracles beside this module, the incidents'
    frozen inputs where the repository keeps them."""
    return Validator().validate(context, decision)


def as_dict_validator(context: IncidentContext):
    """Adapt `validate()` to `evaluation/validation_wiring.py`'s `ValidatorProvider` shape
    (`decision: dict -> {"accepted", "report", "checks_run", "reason_code"}`), for offline
    scoring over decisions held as dicts; the runtime path uses `Validator` directly."""
    def provider(decision: dict) -> dict:
        real_decision = InvestigationDecision(
            disposition=Disposition(decision["disposition"]),
            root_cause_id=decision.get("root_cause_id"),
            root_cause_summary=decision.get("root_cause_summary", ""),
            repair_id=decision.get("repair_id"),
            patch=decision.get("patch") or {},
        )
        result = validate(context, real_decision)
        return {"accepted": result.accepted, "report": result.report,
                "checks_run": list(result.checks_run), "reason_code": result.reason_code}
    return provider
