"""D-17: the failure signal C hands to D's grid runner, one per repeat.

plan_telemetry.md D-17 — "The grid runner — N incidents x R repeats; every
promised repeat is materialised as a record, success or classified
failure; one failing unit does not abort the rest." The grid runner is
D's to build; this module is C's side of that boundary — the shape of
one record for one (incident, repeat) pair, so D never has to reach into
scoring.py or outcome_classification.py directly to get it.

CONFORMANCE.md's own framing of D applies here too: "D is passive. D
records what happened; D must not silently change what A, B or C mean."
So this record carries outcome_classification.py's own category and
sub_kind verbatim, with no additional interpretation layered on for D's
convenience — a signal is exactly what classify_outcome said, addressed
to one incident and one repeat.
"""
from __future__ import annotations

from .outcome_classification import classify_outcome


def build_failure_signal(
    incident_id: str,
    repeat_index: int,
    decision: dict,
    validation: dict | None,
    answer_key: dict,
    judge=None,
) -> dict:
    """Build one machine-readable record for one (incident, repeat) run.

    Returns a strict-JSON-safe dict:
      {"incident_id": str, "repeat_index": int, "category": one of the
       six D-19 names, "sub_kind": str | None, "verdict": the underlying
       score_decision() verdict, "settled_by": "deterministic" | "judge" | "none"}

    This is the complete record for one repeat — D-17 requires every
    promised repeat to become a record, success or classified failure,
    so "success" is returned the same way as every failure category:
    same shape, same fields, nothing conditionally omitted for the
    success case that a failure case would carry, or vice versa.
    """
    classified = classify_outcome(decision, validation, answer_key, judge=judge)

    return {
        "incident_id": incident_id,
        "repeat_index": repeat_index,
        "category": classified["category"],
        "sub_kind": classified["sub_kind"],
        "verdict": classified["verdict"],
        "settled_by": classified["settled_by"],
    }


def build_grid_batch(
    incident_id: str,
    runs: list[tuple[dict, dict | None]],
    answer_key: dict,
    judge=None,
) -> list[dict]:
    """Build one failure signal per repeat for a single incident's grid runs.

    `runs` is a list of (decision, validation) pairs, one per repeat, in
    order — repeat_index is assigned from that order (0-based), matching
    D-17's "every promised repeat is materialised as a record": a caller
    that promised R repeats and passes R (decision, validation) pairs
    gets exactly R records back, one per repeat, in the same order.

    This function performs no filtering and raises nothing itself beyond
    what classify_outcome/score_decision already raise on malformed
    input — D-17 says "one failing unit does not abort the rest", which
    is the grid runner's own retry/isolation responsibility, not this
    function's; this function scores whatever it is handed.
    """
    return [
        build_failure_signal(incident_id, index, decision, validation, answer_key, judge=judge)
        for index, (decision, validation) in enumerate(runs)
    ]
