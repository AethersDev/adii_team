"""Atomic checks a rebuilt world is put through. Each check is a small, pure
function: give it the frozen world and the rebuilt world, get back whether it
passed, its name, and a one-line reason. `validator.py` runs all of them and
accepts only if every one does.

CONFORMANCE C1(c): count alone is not enough — two patches can produce the
same row count while touching different rows. `check_row_identity_matches_intent`
is the one that catches that; `check_record_count_preserved` alone would not.
"""
from __future__ import annotations

from dataclasses import dataclass

from adii.tools import ReadOnlyDatabase


@dataclass(frozen=True)
class CheckOutcome:
    passed: bool
    name: str
    detail: str


def _mart_rows(db: ReadOnlyDatabase) -> dict[str, float]:
    result = db.query("SELECT day, revenue_usd FROM mart_daily ORDER BY day", max_rows=10_000)
    return {day: revenue for day, revenue in result.rows}


def check_record_count_preserved(
        frozen: ReadOnlyDatabase, rebuilt: ReadOnlyDatabase) -> CheckOutcome:
    """The rebuilt world must not have silently gained or lost rows in a table
    the patch was never asked to touch."""
    before = frozen.query("SELECT count(*) FROM orders", max_rows=1).rows[0][0]
    after = rebuilt.query("SELECT count(*) FROM orders", max_rows=1).rows[0][0]
    if before != after:
        return CheckOutcome(False, "record_count_preserved",
                             f"orders row count changed from {before} to {after}; "
                             "a repair to mart_daily's transform must not alter orders")
    return CheckOutcome(True, "record_count_preserved",
                         f"orders row count unchanged at {before}")


def check_row_identity_matches_intent(
        frozen: ReadOnlyDatabase, rebuilt: ReadOnlyDatabase) -> CheckOutcome:
    """Not just how many mart_daily rows exist, but that every one of the SAME
    days (the same identities) still appears — a patch that quietly drops a
    day and computes a coincidentally-matching row count for another must fail
    here, where a count-only oracle would pass it (CONFORMANCE C1c)."""
    before_days = set(_mart_rows(frozen))
    after_days = set(_mart_rows(rebuilt))
    if before_days != after_days:
        missing = before_days - after_days
        added = after_days - before_days
        return CheckOutcome(False, "row_identity_matches_intent",
                             f"mart_daily's days changed: missing {sorted(missing)}, "
                             f"added {sorted(added)} — a repair changes values, not identities")
    return CheckOutcome(True, "row_identity_matches_intent",
                         f"all {len(before_days)} days present in both worlds")


def check_defect_no_longer_reproduces(
        frozen: ReadOnlyDatabase, rebuilt: ReadOnlyDatabase) -> CheckOutcome:
    """The whole point of a REPAIR: after the patch, the number the incident
    was about must actually be right — revenue in dollars equals the order
    count, for the walkthrough world's known-100-cents-per-order fixture."""
    orders_per_day = dict(frozen.query(
        "SELECT order_date, count(*) FROM orders GROUP BY order_date", max_rows=10_000).rows)
    after = _mart_rows(rebuilt)
    wrong = {day: (after.get(day), orders_per_day[day])
             for day in orders_per_day if after.get(day) != float(orders_per_day[day])}
    if wrong:
        return CheckOutcome(False, "defect_no_longer_reproduces",
                             f"revenue still does not equal order count for: {wrong}")
    return CheckOutcome(True, "defect_no_longer_reproduces",
                         "revenue equals order count for every day — the defect is gone")


ALL_CHECKS = (
    check_record_count_preserved,
    check_row_identity_matches_intent,
    check_defect_no_longer_reproduces,
)
