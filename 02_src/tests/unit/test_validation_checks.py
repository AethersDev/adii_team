"""The invariant check, in isolation: two queries that must agree, row for row.

CONFORMANCE C1(c) in test form: a rebuild with the right number of rows and the wrong ones
must fail, where a count-only oracle would wave it through.
"""
from __future__ import annotations

from adii.tools import ReadOnlyDatabase
from adii.validation.checks import Invariant, check

FROZEN = """
CREATE TABLE orders (order_id TEXT PRIMARY KEY, order_date TEXT NOT NULL,
    amount_cents INTEGER NOT NULL);
INSERT INTO orders VALUES ('a', '2026-01-12', 100), ('b', '2026-01-13', 100);
"""
DAYS = Invariant("one_row_per_order_day", "SELECT day FROM mart_daily ORDER BY day",
                 "SELECT DISTINCT order_date FROM orders ORDER BY order_date")


def mart(*rows: str) -> ReadOnlyDatabase:
    return ReadOnlyDatabase.in_memory(
        "CREATE TABLE mart_daily (day TEXT, revenue_usd REAL);\n"
        + "".join(f"INSERT INTO mart_daily VALUES ('{day}', 1.0);\n" for day in rows))


def test_agreeing_rows_pass():
    outcome = check(DAYS, ReadOnlyDatabase.in_memory(FROZEN), mart("2026-01-12", "2026-01-13"))
    assert outcome.passed and outcome.name == "one_row_per_order_day"
    assert outcome.detail == "2 row(s) agree"


def test_the_same_count_with_the_wrong_rows_fails():
    """Both have two rows — a count-only oracle passes this. The identities differ."""
    outcome = check(DAYS, ReadOnlyDatabase.in_memory(FROZEN), mart("2026-01-12", "2026-01-14"))
    assert not outcome.passed
    assert "2026-01-14" in outcome.detail and "2026-01-13" in outcome.detail


def test_a_missing_row_fails_and_says_where():
    outcome = check(DAYS, ReadOnlyDatabase.in_memory(FROZEN), mart("2026-01-12"))
    assert not outcome.passed and "1 row(s) rebuilt against 2 expected" in outcome.detail


def test_a_rebuilt_world_that_cannot_answer_is_a_finding_not_an_error():
    outcome = check(DAYS, ReadOnlyDatabase.in_memory(FROZEN), ReadOnlyDatabase.in_memory(
        "CREATE TABLE mart_daily (revenue_usd REAL);"))
    assert not outcome.passed and "cannot answer" in outcome.detail
