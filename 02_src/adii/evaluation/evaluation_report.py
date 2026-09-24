"""D-19: the M10 report, built from a real RunRecord plus an answer key.

build_plan.md M10 and plan_telemetry.md D-19 both require the final
report to show "success, failure, false repair, correct abstention,
unnecessary escalation and repair rejection... each labelled in its own
terms." This module is that report's evaluation half, built from C's own
scoring output — outcome_classification.classify_outcome — applied to a
real run record document (02_src/adii/reporting/record.py, any version it reads).

The record carries no evaluation, by design: the evaluation authority is a separate
program. This module reads a record's JSON as it is and writes a SEPARATE document,
adii.evaluation_report/v1, beside record.json in the archive (evaluation_report.json).

Only "submitted" runs (RunRecord.termination == "submitted") carry a
decision to evaluate at all — see TERMINATIONS in record.py. A run that
ended any other way (model_failure, bound_hit, infrastructure_failure)
has nothing for classify_outcome to score, and this module says so
explicitly rather than inventing a category for it.
"""
from __future__ import annotations

import json

from .grounding import check_grounding
from .outcome_classification import classify_outcome

SCHEMA = "adii.evaluation_report/v1"

# A run that did not submit carries no decision to score (record.py, TERMINATIONS).
NON_SUBMITTED_CATEGORY = "not_evaluable"


def build_evaluation_report(run_record: dict, answer_key: dict, judge=None,
                            grounding_key: dict | None = None) -> dict:
    """Build one adii.evaluation_report/v1 document from a RunRecord's own
    JSON shape (as produced by RunRecord.to_json() / read back by
    from_json()) and an answer key.

    `run_record` is a dict with at least "label", "termination", and
    "decision"/"validation" in the exact shape RunRecord.to_json() emits:
    decision = {"disposition": ..., "root_cause_id": ..., "repair_id": ...,
    "patch": ...} or None; validation = {"accepted": ..., "report": ...,
    "checks_run": [...]} or None.

    Returns:
      {"schema": "adii.evaluation_report/v1", "run_label": str,
       "incident_id": str, "category": ..., "sub_kind": ..., "verdict": ...,
       "settled_by": ..., "runtime_validation": {...}}
    for a submitted run, or
      {"schema": "adii.evaluation_report/v1", "run_label": str,
       "incident_id": str, "category": "not_evaluable",
       "reason": "termination was <x>, not submitted",
       "runtime_validation": {...}}
    for a run with no decision to score.

    `runtime_validation` is a dimension orthogonal to the verdict: what the runtime's
    validator did with the decision before anyone scored it — "none" (no repair, so
    nothing to check), "unchecked" (a repair nobody checked: accepted false with no
    checks run — the runtime's placeholder until a validator exists), or "checked" (a
    verdict, accepted or not, with the checks that produced it). The same evaluation
    category — an unwarranted repair, say — means a different system behaviour depending
    on whether the runtime blocked it before action or merely preserved it for this
    scorer to find; this field is what lets that be counted.

    Raises ValueError if run_record is missing "termination", "label", or
    "context" — the same "fail loudly, name the field" style the rest of
    this directory's loaders use, rather than a bare KeyError.
    """
    for field in ("label", "termination", "context"):
        if field not in run_record:
            raise ValueError(f"run_record is missing required field {field!r}")

    incident_id = run_record["context"]["incident_id"]
    label = run_record["label"]
    runtime_validation = describe_runtime_validation(run_record.get("validation"))

    if run_record["termination"] != "submitted":
        return {
            "schema": SCHEMA,
            "run_label": label,
            "incident_id": incident_id,
            "category": NON_SUBMITTED_CATEGORY,
            "reason": (
                f"termination was {run_record['termination']!r}, "
                "not 'submitted' — no decision to evaluate"
            ),
            "runtime_validation": runtime_validation,
        }

    decision = run_record["decision"]
    validation = run_record["validation"]
    classified = classify_outcome(decision, validation, answer_key, judge=judge)

    return {
        "schema": SCHEMA,
        "run_label": label,
        "incident_id": incident_id,
        "category": classified["category"],
        "sub_kind": classified["sub_kind"],
        "verdict": classified["verdict"],
        "settled_by": classified["settled_by"],
        "runtime_validation": runtime_validation,
        "grounding": describe_grounding(decision, run_record.get("trace", []), grounding_key),
    }


def describe_runtime_validation(validation: dict | None) -> dict:
    """What the runtime's validator did with the decision, as the record states it —
    never inferred from the category."""
    if validation is None:
        return {"state": "none", "accepted": None, "checks_run": []}
    checks = list(validation.get("checks_run") or [])
    accepted = bool(validation.get("accepted"))
    if not accepted and validation.get("reason_code"):
        state = "not_checkable"          # the validator had no world to rebuild, in structure
    elif not accepted and not checks:
        state = "unchecked"              # the legacy placeholder, records before 22 Sep
    else:
        state = "checked"
    return {"state": state, "accepted": accepted, "checks_run": checks}


def describe_grounding(decision: dict, trace: list[dict] | None = None,
                       grounding_key: dict | None = None) -> dict:
    """What the decision cites, as the record states it — a dimension beside the category,
    never inside it: a correct disposition with nothing cited is not a grounded success.
    `grounded` means at least one observation is cited; the record refuses a citation its
    trace never minted, so every cited id resolves. Whether the cited observations warrant
    the conclusion is a further question, the evaluation authority's — a grounding key's."""
    refs = list(decision.get("evidence_refs") or [])       # absent in records before 22 Sep
    grounding = {"evidence_refs": refs, "grounded": bool(refs)}
    if grounding_key is not None:        # the decisive observations, read from the trace
        grounding["decisive"] = check_grounding(trace or [], grounding_key, refs)
    return grounding


def to_json(report: dict) -> str:
    """Strict RFC 8259, matching RunRecord.to_json()'s own convention:
    two-space indent, non-ASCII preserved, NaN/Infinity refused before
    anything reaches a sink."""
    return json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
