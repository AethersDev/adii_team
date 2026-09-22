"""Step 2 of building validation/: apply_patch rebuilds a brand-new world from a candidate
patch, never mutating the investigator's own database connection.

The patch is what the protocol tells a model to send — the permitted path mapped to the
transform's full new contents — so the reference repair committed with the walkthrough is
the accepted case here, verbatim, and a model's SQL is what every rejection is measured on.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from adii.tools.errors import Denied
from adii.tools.walkthrough_world import ORDERS_PER_DAY
from adii.validation.patching import (
    MAX_BUILD_TICKS,
    TRANSFORM,
    PatchRejected,
    apply_patch,
    build_patched_script,
    transform_of,
)

WALKTHROUGH = Path(__file__).resolve().parents[3] / "01_data" / "walkthrough"
# The reference repair, as committed with the teaching fixture: one conversion, cents to
# dollars. The defective transform divides by 100 twice.
CORRECT_PATCH = json.loads((WALKTHROUGH / "decision.json").read_text(encoding="utf-8"))["patch"]
STILL_BROKEN_PATCH = {TRANSFORM: "SELECT order_id, order_date, amount_cents / 100.0 / 100.0 "
                                 "AS amount_usd FROM orders;"}


class TestTransformOf:
    def test_the_walkthroughs_own_repair_names_the_permitted_transform(self):
        assert set(CORRECT_PATCH) == {TRANSFORM}
        assert transform_of(CORRECT_PATCH).startswith("SELECT ")

    def test_a_trailing_semicolon_and_whitespace_are_the_files_not_a_second_statement(self):
        assert transform_of({TRANSFORM: "  SELECT 1 AS amount_usd FROM orders ;\n"}) == \
            "SELECT 1 AS amount_usd FROM orders"

    @pytest.mark.parametrize("patch", [
        {},
        {"some_other_file.sql": "SELECT 1"},
        {"stg_orders.sql": "SELECT 1"},                       # the bare name is not the path
        {TRANSFORM: "SELECT 1", "jobs/load.yml": "rerun"},     # a second file
    ])
    def test_anything_but_exactly_the_permitted_transform_is_rejected(self, patch):
        with pytest.raises(PatchRejected, match=TRANSFORM):
            transform_of(patch)

    @pytest.mark.parametrize("contents", ["", "   ", ";", "\n;\n"])
    def test_an_empty_file_is_rejected(self, contents):
        with pytest.raises(PatchRejected, match="empty"):
            transform_of({TRANSFORM: contents})

    def test_a_second_statement_is_rejected_before_anything_runs(self):
        with pytest.raises(PatchRejected, match="one statement"):
            transform_of({TRANSFORM: "SELECT * FROM orders; DROP TABLE orders"})

    def test_a_semicolon_in_a_comment_or_a_literal_is_not_a_second_statement(self):
        """Models write comments; a separator inside one, or inside a string, is text."""
        commented = ("-- cents; not dollars\n/* one; two */\nSELECT order_id, order_date, "
                     "amount_cents / 100.0 AS amount_usd, 'a;b' AS note FROM orders; -- done;")
        assert transform_of({TRANSFORM: commented}).startswith("-- cents; not dollars")
        assert apply_patch({TRANSFORM: commented}).query(
            "SELECT count(*) FROM mart_daily", max_rows=1).rows[0][0] == len(ORDERS_PER_DAY)

    @pytest.mark.parametrize("contents", ["-- only a comment", "/* nothing */", "-- a;\n;"])
    def test_a_file_that_is_only_comments_is_empty(self, contents):
        with pytest.raises(PatchRejected, match="empty"):
            transform_of({TRANSFORM: contents})


class TestBuildPatchedScript:
    def test_the_script_runs_the_candidate_as_the_staging_transform_then_derives_the_mart(self):
        script = build_patched_script(CORRECT_PATCH)
        assert "CREATE TABLE stg_orders AS SELECT order_id, order_date, amount_cents / 100.0 " \
               "AS amount_usd FROM orders;" in script
        assert script.rstrip().endswith("FROM stg_orders GROUP BY order_date;")
        assert script.index("INSERT INTO orders") < script.index("CREATE TABLE stg_orders") \
            < script.index("CREATE TABLE mart_daily")


class TestApplyPatch:
    def test_the_walkthroughs_own_repair_produces_a_world_with_correct_revenue(self):
        db = apply_patch(CORRECT_PATCH)
        rows = db.query("SELECT day, revenue_usd FROM mart_daily ORDER BY day", max_rows=10).rows
        for (day, count), (result_day, revenue) in zip(ORDERS_PER_DAY, rows, strict=True):
            assert result_day == day
            assert revenue == float(count)     # 100-cent orders: dollars per day = orders per day

    def test_a_patch_that_does_not_fix_the_defect_still_applies_but_stays_wrong(self):
        # apply_patch's job is only "did this patch build a world at all" — whether the
        # resulting numbers are RIGHT is checks.py's job (step 3).
        db = apply_patch(STILL_BROKEN_PATCH)
        rows = db.query("SELECT day, revenue_usd FROM mart_daily ORDER BY day", max_rows=10).rows
        for (_day, count), (_result_day, revenue) in zip(ORDERS_PER_DAY, rows, strict=True):
            assert revenue != float(count)

    def test_a_cte_is_one_statement_and_applies(self):
        db = apply_patch({TRANSFORM: "WITH o AS (SELECT * FROM orders) SELECT order_id, "
                                     "order_date, amount_cents / 100.0 AS amount_usd FROM o"})
        assert db.query("SELECT count(*) FROM mart_daily", max_rows=1).rows[0][0] == \
            len(ORDERS_PER_DAY)

    @pytest.mark.parametrize("sql, why", [
        ("SELECT order_id, order_date, amount_cents FROM orders", "amount_usd"),   # no amount_usd
        ("SELECT order_id, amount_cents / 100.0 AS amount_usd FROM orders", "order_date"),
        ("SELECT * FROM no_such_table", "no such table"),
        ("SELEC order_id FROM orders", "syntax"),
    ])
    def test_a_transform_the_world_cannot_run_is_rejected_in_sqlites_words(self, sql, why):
        with pytest.raises(PatchRejected, match=why):
            apply_patch({TRANSFORM: sql})

    def test_a_transform_that_never_finishes_is_refused_at_the_budget_not_waited_for(self):
        # a self-join cubed: the frozen orders make more rows than the budget allows
        runaway = {TRANSFORM: "SELECT a.order_id, a.order_date, a.amount_cents / 100.0 AS "
                              "amount_usd FROM orders a, orders b, orders c"}
        assert MAX_BUILD_TICKS > 0
        with pytest.raises(PatchRejected, match="interrupted"):
            apply_patch(runaway)

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
