"""Step 2 of building validation/: apply_patch rebuilds a brand-new world from
a candidate patch, never mutating the investigator's own database connection.
"""
from __future__ import annotations

import pytest
from adii.tools.errors import Denied
from adii.tools.walkthrough_world import ORDERS_PER_DAY
from adii.validation.patching import (
    PatchRejected,
    apply_patch,
    build_patched_script,
    evaluate_patch_expression,
)

CORRECT_PATCH = {"stg_orders.sql": "count * 100 / 100"}
STILL_BROKEN_PATCH = {"stg_orders.sql": "count * 100 / 100 / 100"}


class TestEvaluatePatchExpression:
    def test_plain_arithmetic_evaluates(self):
        assert evaluate_patch_expression("count * 100 / 100", 298) == 298.0

    def test_only_count_and_literals_and_arithmetic_are_allowed(self):
        assert evaluate_patch_expression("1 + 2 * 3", 0) == 7.0
        assert evaluate_patch_expression("-count", 5) == -5.0

    @pytest.mark.parametrize("expression", [
        "__import__('os').system('echo hi')",
        "open('secret').read()",
        "count.__class__",
        "[x for x in range(10)]",
        "count if True else 0",
        "",
        "not count",
    ])
    def test_anything_beyond_arithmetic_is_rejected(self, expression):
        with pytest.raises(PatchRejected):
            evaluate_patch_expression(expression, 10)

    def test_a_syntax_error_is_rejected_not_raised_as_a_python_exception(self):
        with pytest.raises(PatchRejected):
            evaluate_patch_expression("count * / 100", 10)


class TestBuildPatchedScript:
    def test_an_unrecognised_patch_target_is_rejected(self):
        with pytest.raises(PatchRejected, match="stg_orders.sql"):
            build_patched_script({"some_other_file.sql": "count"})

    def test_an_empty_patch_is_rejected(self):
        with pytest.raises(PatchRejected):
            build_patched_script({})

    def test_the_correct_single_division_patch_builds_a_script_with_right_revenue(self):
        script = build_patched_script(CORRECT_PATCH)
        for day, count in ORDERS_PER_DAY:
            assert f"'{day}', {float(count)})" in script


class TestApplyPatch:
    def test_the_correct_patch_produces_a_world_with_correct_revenue(self):
        db = apply_patch(CORRECT_PATCH)
        rows = db.query("SELECT day, revenue_usd FROM mart_daily ORDER BY day", max_rows=10).rows
        for (day, count), (result_day, revenue) in zip(ORDERS_PER_DAY, rows, strict=True):
            assert result_day == day
            assert revenue == float(count)

    def test_a_patch_that_does_not_fix_the_defect_still_applies_but_stays_wrong(self):
        # apply_patch's job is only "did this patch build a world at all" —
        # whether the resulting numbers are RIGHT is checks.py's job (step 3).
        db = apply_patch(STILL_BROKEN_PATCH)
        rows = db.query("SELECT day, revenue_usd FROM mart_daily ORDER BY day", max_rows=10).rows
        for (_day, count), (_result_day, revenue) in zip(ORDERS_PER_DAY, rows, strict=True):
            assert revenue != float(count)  # still broken — apply_patch does not judge this

    def test_an_unrejected_patch_returns_a_read_only_database(self):
        db = apply_patch(CORRECT_PATCH)
        with pytest.raises(Denied):
            db.query("INSERT INTO orders VALUES ('x', '2026-01-12', 1)", max_rows=1)

    def test_two_applications_of_the_same_patch_are_independent(self):
        first = apply_patch(CORRECT_PATCH)
        second = apply_patch(CORRECT_PATCH)
        first_rows = first.query("SELECT * FROM mart_daily", max_rows=10).rows
        second_rows = second.query("SELECT * FROM mart_daily", max_rows=10).rows
        assert first_rows == second_rows
