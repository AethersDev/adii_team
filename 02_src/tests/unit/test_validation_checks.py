"""Step 3 of building validation/: the atomic checks, each in isolation.

CONFORMANCE C1(c) in test form: a correct-count-wrong-identity rebuild must be
caught by check_row_identity_matches_intent even where a count-only oracle
would wave it through.
"""
from __future__ import annotations

from adii.tools import ReadOnlyDatabase, open_walkthrough_world
from adii.validation.checks import (
    ALL_CHECKS,
    check_defect_no_longer_reproduces,
    check_record_count_preserved,
    check_row_identity_matches_intent,
)
from adii.validation.patching import apply_patch

TRANSFORM = "transforms/stg_orders.sql"
CORRECT_PATCH = {TRANSFORM: "SELECT order_id, order_date, amount_cents / 100.0 AS amount_usd "
                           "FROM orders;"}
STILL_BROKEN_PATCH = {TRANSFORM: "SELECT order_id, order_date, amount_cents / 100.0 / 100.0 "
                                "AS amount_usd FROM orders;"}

# A rebuild that drops a day but happens to land on a matching total row
# count elsewhere is simulated directly against a hand-built world, since
# the walkthrough patch surface cannot itself drop a day.
FROZEN_SCRIPT = """
CREATE TABLE orders (order_id TEXT PRIMARY KEY, order_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL);
CREATE TABLE mart_daily (day TEXT PRIMARY KEY, revenue_usd REAL NOT NULL);
INSERT INTO orders VALUES ('a', '2026-01-12', 100), ('b', '2026-01-13', 100);
INSERT INTO mart_daily VALUES ('2026-01-12', 0.01), ('2026-01-13', 0.01);
"""

# Same row COUNT (2) as frozen, but the second row's identity ("day") is
# different — 01-14 instead of 01-13. A count-only check cannot tell these
# apart; identity can.
WRONG_IDENTITY_SCRIPT = """
CREATE TABLE orders (order_id TEXT PRIMARY KEY, order_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL);
CREATE TABLE mart_daily (day TEXT PRIMARY KEY, revenue_usd REAL NOT NULL);
INSERT INTO orders VALUES ('a', '2026-01-12', 100), ('b', '2026-01-13', 100);
INSERT INTO mart_daily VALUES ('2026-01-12', 1.0), ('2026-01-14', 1.0);
"""


class TestCheckRecordCountPreserved:
    def test_passes_when_orders_row_count_is_unchanged(self):
        frozen = open_walkthrough_world()
        rebuilt = apply_patch(CORRECT_PATCH)
        outcome = check_record_count_preserved(frozen, rebuilt)
        assert outcome.passed is True

    def test_fails_when_a_row_disappears(self):
        frozen = ReadOnlyDatabase.in_memory(FROZEN_SCRIPT)
        fewer_rows_script = FROZEN_SCRIPT.replace(
            "INSERT INTO orders VALUES ('a', '2026-01-12', 100), ('b', '2026-01-13', 100);",
            "INSERT INTO orders VALUES ('a', '2026-01-12', 100);")
        rebuilt = ReadOnlyDatabase.in_memory(fewer_rows_script)
        outcome = check_record_count_preserved(frozen, rebuilt)
        assert outcome.passed is False


class TestCheckRowIdentityMatchesIntent:
    def test_passes_when_the_same_days_survive(self):
        frozen = ReadOnlyDatabase.in_memory(FROZEN_SCRIPT)
        rebuilt = ReadOnlyDatabase.in_memory(FROZEN_SCRIPT)
        outcome = check_row_identity_matches_intent(frozen, rebuilt)
        assert outcome.passed is True

    def test_fails_on_same_count_but_wrong_identity(self):
        # CONFORMANCE C1(c): both worlds have exactly 2 mart_daily rows — a
        # count-only oracle passes this. Identity must not.
        frozen = ReadOnlyDatabase.in_memory(FROZEN_SCRIPT)
        rebuilt = ReadOnlyDatabase.in_memory(WRONG_IDENTITY_SCRIPT)

        count_before = frozen.query("SELECT count(*) FROM mart_daily", max_rows=1).rows[0][0]
        count_after = rebuilt.query("SELECT count(*) FROM mart_daily", max_rows=1).rows[0][0]
        assert count_before == count_after  # the count-only oracle would pass this

        outcome = check_row_identity_matches_intent(frozen, rebuilt)
        assert outcome.passed is False
        assert "2026-01-13" in outcome.detail or "2026-01-14" in outcome.detail


class TestCheckDefectNoLongerReproduces:
    def test_fails_against_the_unpatched_defect(self):
        frozen = open_walkthrough_world()
        outcome = check_defect_no_longer_reproduces(frozen, frozen)
        assert outcome.passed is False

    def test_fails_when_the_patch_does_not_actually_fix_it(self):
        frozen = open_walkthrough_world()
        rebuilt = apply_patch(STILL_BROKEN_PATCH)
        outcome = check_defect_no_longer_reproduces(frozen, rebuilt)
        assert outcome.passed is False

    def test_passes_when_the_patch_fixes_it(self):
        frozen = open_walkthrough_world()
        rebuilt = apply_patch(CORRECT_PATCH)
        outcome = check_defect_no_longer_reproduces(frozen, rebuilt)
        assert outcome.passed is True


class TestAllChecksTogether:
    def test_the_correct_patch_passes_every_check(self):
        frozen = open_walkthrough_world()
        rebuilt = apply_patch(CORRECT_PATCH)
        outcomes = [check(frozen, rebuilt) for check in ALL_CHECKS]
        assert all(outcome.passed for outcome in outcomes)

    def test_the_still_broken_patch_fails_at_least_one_check(self):
        frozen = open_walkthrough_world()
        rebuilt = apply_patch(STILL_BROKEN_PATCH)
        outcomes = [check(frozen, rebuilt) for check in ALL_CHECKS]
        assert not all(outcome.passed for outcome in outcomes)
