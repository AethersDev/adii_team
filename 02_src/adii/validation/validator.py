"""The independent authority: satisfies `runtime.run.Validator`.

CONFORMANCE C1. The investigator hands over a `REPAIR` decision and this is
the only place that decides whether it holds. It rebuilds the world from
frozen inputs (`patching.apply_patch`), runs every check (`checks.ALL_CHECKS`)
against the rebuild, and returns `ACCEPT` only if every one passes.

`validate()`'s signature is `(context, decision) -> ValidationResult` — the
shape `runtime/run.py`'s `Validator` protocol requires, and the shape
`ScriptedValidator` already stands in for. Nothing here reads `decision`'s
prose (`root_cause_summary`) or any rehearsal the investigator might have run
in its own sandbox: only `decision.patch` reaches `patching.apply_patch`, and
that function has no parameter through which a rehearsal claim could arrive.
"""
from __future__ import annotations

from adii.contracts import Disposition, IncidentContext, InvestigationDecision, ValidationResult
from adii.tools import open_walkthrough_world

from .checks import ALL_CHECKS
from .patching import PatchRejected, apply_patch

# The frozen world each known incident rebuilds from. Keyed by incident_id, not
# by anything the investigator supplies — the investigator's IncidentContext
# only carries incident_id, alert and as_of, never a path into this table.
_WORLD_BUILDERS = {
    "demo-learning-001": open_walkthrough_world,
}


class UnknownIncident(Exception):
    """Validation has no frozen world to rebuild for this incident_id. This is
    an infrastructure gap, not a verdict — the run_incident() runtime records
    it as an infrastructure_failure rather than a REJECT with reasons."""


def validate(context: IncidentContext, decision: InvestigationDecision) -> ValidationResult:
    """Rebuild `context.incident_id`'s frozen world with `decision.patch`
    applied, run every check, and return the verdict. Raises `UnknownIncident`
    if this validator has no frozen world for the incident — never silently
    accepts or rejects an incident it cannot rebuild."""
    if context.incident_id not in _WORLD_BUILDERS:
        raise UnknownIncident(
            f"validation has no frozen world for incident_id={context.incident_id!r}")
    frozen = _WORLD_BUILDERS[context.incident_id]()

    # the rebuild is the first check: a patch the world cannot apply is a rejection by the
    # check named `rebuild`, never the legacy "nothing checked" shape
    try:
        rebuilt = apply_patch(decision.patch)
    except PatchRejected as problem:
        return ValidationResult(accepted=False, report=f"rebuild: patch rejected: {problem}",
                                 checks_run=("rebuild",))

    outcomes = [check(frozen, rebuilt) for check in ALL_CHECKS]
    accepted = all(outcome.passed for outcome in outcomes)
    report = "rebuild: the world rebuilt with the patch applied; " + \
        "; ".join(outcome.detail for outcome in outcomes)
    checks_run = ("rebuild", *(outcome.name for outcome in outcomes))
    return ValidationResult(accepted=accepted, report=report, checks_run=checks_run)


class Validator:
    """The object shape `run_incident()` calls: `validator.validate(context,
    decision)`. A thin wrapper around the module-level function above, so
    `runtime/__main__.py` can hand in `Validator()` the same way it hands in
    `ScriptedValidator(...)`."""

    def validate(self, context: IncidentContext,
                 decision: InvestigationDecision) -> ValidationResult:
        return validate(context, decision)


def as_dict_validator(context: IncidentContext):
    """Adapt `validate()` to `evaluation/validation_wiring.py`'s
    `ValidatorProvider` shape (`decision: dict -> {"accepted", "report",
    "checks_run"}`), for callers working with decisions as dicts — offline
    scoring scripts, fixtures — rather than with a live `IncidentContext`.

    `context` is fixed at adaptation time because `ValidatorProvider` only
    takes a decision, not a context; the runtime path (`Validator` above)
    should be preferred wherever a real `IncidentContext` is already at hand.
    Swapping this in for
    `validation_wiring.fake_validator_accepts_everything_structurally_sound`
    is the one-line change that module's own docstring promises.
    """
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
