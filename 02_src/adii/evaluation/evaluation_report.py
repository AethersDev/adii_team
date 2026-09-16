"""D-19: the M10 report, built from a real RunRecord plus an answer key.

build_plan.md M10 and plan_telemetry.md D-19 both require the final
report to show "success, failure, false repair, correct abstention,
unnecessary escalation and repair rejection... each labelled in its own
terms." This module is that report's evaluation half, built from C's own
scoring output — outcome_classification.classify_outcome — applied to a
real adii.run_record/v1 document (02_src/adii/reporting/record.py).

Deliberately NOT a change to RunRecord or its schema: RunRecord v1, as it
exists in the real codebase today, carries no evaluation field at all —
adding one is a schema change (v1 -> v2) that touches record.py,
render.py, every archived v1 file, and the inspector, which is a decision
for whoever owns reporting/, not something this module does unilaterally.
This module instead reads a RunRecord's JSON as-is and produces a
SEPARATE document, adii.evaluation_report/v1, meant to sit beside
record.json in the archive (e.g. evaluation_report.json) until the team
decides whether and how to fold it into RunRecord itself. Nothing here
depends on that decision being made any particular way.

Only "submitted" runs (RunRecord.termination == "submitted") carry a
decision to evaluate at all — see TERMINATIONS in record.py. A run that
ended any other way (model_failure, bound_hit, infrastructure_failure)
has nothing for classify_outcome to score, and this module says so
explicitly rather than inventing a category for it.
"""
from __future__ import annotations

import json

from .outcome_classification import classify_outcome

SCHEMA = "adii.evaluation_report/v1"

# Mirrors record.py's own TERMINATIONS — only "submitted" runs carry a
# decision. Duplicated here rather than imported: this module has no
# dependency on the adii_team package, by the same separation C2/C3 rest
# on (evaluation authority lives outside the system it evaluates).
NON_SUBMITTED_CATEGORY = "not_evaluable"


def build_evaluation_report(run_record: dict, answer_key: dict, judge=None) -> dict:
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
       "settled_by": ...}
    for a submitted run, or
      {"schema": "adii.evaluation_report/v1", "run_label": str,
       "incident_id": str, "category": "not_evaluable",
       "reason": "termination was <x>, not submitted"}
    for a run with no decision to score.

    Raises ValueError if run_record is missing "termination", "label", or
    "context" — the same "fail loudly, name the field" style the rest of
    this directory's loaders use, rather than a bare KeyError.
    """
    for field in ("label", "termination", "context"):
        if field not in run_record:
            raise ValueError(f"run_record is missing required field {field!r}")

    incident_id = run_record["context"]["incident_id"]
    label = run_record["label"]

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
    }


def to_json(report: dict) -> str:
    """Strict RFC 8259, matching RunRecord.to_json()'s own convention:
    two-space indent, non-ASCII preserved, NaN/Infinity refused before
    anything reaches a sink."""
    return json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
