"""apply_patch rebuilds a brand-new world from an incident's frozen inputs with a candidate
patch applied, never mutating the investigator's own database connection.

The pipeline, the world and the transforms here are the walkthrough's, read the way the
validator reads them, so the reference repair committed with the teaching fixture is the
accepted case, verbatim, and a model's SQL is what every rejection is measured on.
"""
from __future__ import annotations

import json

import pytest
from adii.tools.errors import Denied
from adii.tools.walkthrough_world import ORDERS_PER_DAY
from adii.validation.patching import (
    MAX_BUILD_TICKS,
    PatchRejected,
    apply_patch,
    one_statement,
    path_of,
    rebuild_script,
)
from adii.validation.validator import ORACLES, WALKTHROUGH, Validator, load_oracle

PIPELINE, _ = load_oracle(ORACLES / f"{WALKTHROUGH[0]}.json")
WORLD, TRANSFORMS = Validator().frozen_inputs(WALKTHROUGH[0])
TRANSFORM = path_of("stg_orders")
CORRECT_PATCH = json.loads((WALKTHROUGH[1] / "decision.json").read_text(encoding="utf-8"))["patch"]
STILL_BROKEN_PATCH = {TRANSFORM: "SELECT order_id, order_date, amount_cents / 100.0 / 100.0 "
                                 "AS amount_usd FROM orders;"}


def rebuilt(patch):
    return apply_patch(WORLD, PIPELINE, TRANSFORMS, patch)


class TestOneStatement:
    def test_a_trailing_semicolon_and_whitespace_are_the_files_not_a_second_statement(self):
        assert one_statement(TRANSFORM, "  SELECT 1 AS amount_usd FROM orders ;\n") == \
            "SELECT 1 AS amount_usd FROM orders"

    @pytest.mark.parametrize("contents", ["", "   ", ";", "\n;\n", "-- only a comment",
                                          "/* nothing */", "-- a;\n;"])
    def test_an_empty_file_is_rejected(self, contents):
        with pytest.raises(PatchRejected, match="empty"):
            one_statement(TRANSFORM, contents)

    def test_a_second_statement_is_rejected_before_anything_runs(self):
        with pytest.raises(PatchRejected, match="one statement"):
            one_statement(TRANSFORM, "SELECT * FROM orders; DROP TABLE orders")

    def test_a_semicolon_in_a_comment_or_a_literal_is_not_a_second_statement(self):
        """Models write comments; a separator inside one, or inside a string, is text."""
        commented = ("-- cents; not dollars\n/* one; two */\nSELECT order_id, order_date, "
                     "amount_cents / 100.0 AS amount_usd, 'a;b' AS note FROM orders; -- done;")
        assert one_statement(TRANSFORM, commented).startswith("-- cents; not dollars")
        assert rebuilt({TRANSFORM: commented}).query(
            "SELECT count(*) FROM mart_daily", max_rows=1).rows[0][0] == len(ORDERS_PER_DAY)


class TestRebuildScript:
    @pytest.mark.parametrize("patch", [
        {},
        {"some_other_file.sql": "SELECT 1"},
        {"stg_orders.sql": "SELECT 1"},                           # the bare name is not the path
        {TRANSFORM: "SELECT 1", "jobs/load.yml": "rerun"},         # a path nothing derives from
        {path_of("mart_daily"): "SELECT 1"},                       # the pipeline's own SQL
    ])
    def test_a_patch_may_replace_only_a_transform_the_pipeline_derives(self, patch):
        with pytest.raises(PatchRejected, match="transforms/stg_orders.sql"):
            rebuild_script(WORLD, PIPELINE, TRANSFORMS, patch)

    def test_the_world_comes_first_then_every_derived_table_dropped_and_derived_again(self):
        script = rebuild_script(WORLD, PIPELINE, TRANSFORMS, CORRECT_PATCH)
        assert script.startswith(WORLD)
        assert 'CREATE TABLE "stg_orders" AS SELECT order_id, order_date, amount_cents / 100.0 ' \
               'AS amount_usd FROM orders;' in script
        assert script.index('DROP TABLE IF EXISTS "mart_daily"') \
            < script.index('CREATE TABLE "stg_orders"') < script.index('CREATE TABLE "mart_daily"')


class TestApplyPatch:
    def test_the_walkthroughs_own_repair_produces_a_world_with_correct_revenue(self):
        rows = rebuilt(CORRECT_PATCH).query("SELECT day, revenue_usd FROM mart_daily ORDER BY day",
                                            max_rows=10).rows
        for (day, count), (result_day, revenue) in zip(ORDERS_PER_DAY, rows, strict=True):
            assert (result_day, revenue) == (day, float(count))

    def test_a_patch_that_does_not_fix_the_defect_still_applies_but_stays_wrong(self):
        rows = rebuilt(STILL_BROKEN_PATCH).query("SELECT revenue_usd FROM mart_daily ORDER BY day",
                                                 max_rows=10).rows
        assert all(revenue != float(count)
                   for (_d, count), (revenue,) in zip(ORDERS_PER_DAY, rows, strict=True))

    def test_the_frozen_transform_applied_as_is_reproduces_the_incident(self):
        rows = rebuilt({TRANSFORM: TRANSFORMS["stg_orders"]}).query(
            "SELECT revenue_usd FROM mart_daily ORDER BY day", max_rows=10).rows
        assert [revenue for (revenue,) in rows] == \
            pytest.approx([count / 100 for _d, count in ORDERS_PER_DAY])

    @pytest.mark.parametrize("sql, why", [
        ("SELECT order_id, order_date, amount_cents FROM orders", "amount_usd"),
        ("SELECT order_id, amount_cents / 100.0 AS amount_usd FROM orders", "order_date"),
        ("SELECT * FROM no_such_table", "no such table"),
        ("SELEC order_id FROM orders", "syntax"),
    ])
    def test_a_transform_the_world_cannot_run_is_rejected_in_sqlites_words(self, sql, why):
        with pytest.raises(PatchRejected, match=why):
            rebuilt({TRANSFORM: sql})

    def test_a_transform_that_never_finishes_is_refused_at_the_budget_not_waited_for(self):
        runaway = {TRANSFORM: "SELECT a.order_id, a.order_date, a.amount_cents / 100.0 AS "
                              "amount_usd FROM orders a, orders b, orders c"}
        assert MAX_BUILD_TICKS > 0
        with pytest.raises(PatchRejected, match="interrupted"):
            rebuilt(runaway)

    def test_an_unrejected_patch_returns_a_read_only_database(self):
        with pytest.raises(Denied):
            rebuilt(CORRECT_PATCH).query("INSERT INTO orders VALUES ('x', '2026-01-12', 1)",
                                         max_rows=1)

    def test_two_applications_of_the_same_patch_are_independent(self):
        first = rebuilt(CORRECT_PATCH).query("SELECT * FROM mart_daily", max_rows=10).rows
        assert first == rebuilt(CORRECT_PATCH).query("SELECT * FROM mart_daily", max_rows=10).rows
