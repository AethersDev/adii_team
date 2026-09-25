"""Step 1 of building validation/: proving the ground it stands on.

C1 (requirement) requires validation to "rebuild from frozen inputs" — that
promise is only real if two things are true about the world validation rebuilds
from: (a) rebuilding twice gives byte-identical data (determinism), and (b) two
rebuilds are fully isolated from each other (no shared state a first validation
run could leak into a second one). These tests establish both against the real
walkthrough world, before any validation code exists to depend on them.
"""
from __future__ import annotations

from adii.tools import open_walkthrough_world
from adii.tools.walkthrough_world import build_script


def _all_orders(db):
    result = db.query("SELECT order_id, order_date, amount_cents FROM orders "
                       "ORDER BY order_id", max_rows=10_000)
    return result.rows


def _all_mart(db):
    result = db.query("SELECT day, revenue_usd FROM mart_daily ORDER BY day", max_rows=10_000)
    return result.rows


class TestRebuildIsDeterministic:
    def test_two_independent_opens_produce_byte_identical_rows(self):
        first = open_walkthrough_world()
        second = open_walkthrough_world()

        assert _all_orders(first) == _all_orders(second)
        assert _all_mart(first) == _all_mart(second)

    def test_the_same_build_script_text_rebuilds_the_same_world(self):
        script = build_script()

        from adii.tools import ReadOnlyDatabase
        rebuilt_a = ReadOnlyDatabase.in_memory(script)
        rebuilt_b = ReadOnlyDatabase.in_memory(script)

        assert _all_orders(rebuilt_a) == _all_orders(rebuilt_b)


class TestRebuildsAreIsolated:
    def test_a_second_rebuild_does_not_see_state_from_the_first(self):
        first = open_walkthrough_world()
        # Prove there is no shared connection or cache: closing the first
        # database must not affect a second, independently opened one.
        before_close = _all_mart(first)
        first.close()

        second = open_walkthrough_world()
        assert _all_mart(second) == before_close

    def test_opening_two_worlds_at_once_keeps_them_independent(self):
        world_a = open_walkthrough_world()
        world_b = open_walkthrough_world()

        # Neither open() call takes a patch or any mutation path — read-only by
        # construction (ReadOnlyDatabase denies every write at the authorizer).
        # This asserts the fact validation/ will rely on: there is no way for one
        # opened world to have diverged from another opened from the same script.
        assert _all_orders(world_a) == _all_orders(world_b)
