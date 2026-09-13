"""The tiny local database behind `demo-learning-001`, the walkthrough incident.

This is the world the fixture in `01_data/walkthrough/` was recorded against, rebuilt as
SQL so the same investigation can be run through real tools instead of replayed from a
trace. It is deliberately trivial: every order is exactly 100 cents, so daily revenue in
dollars equals the daily order count, and the staging transform divides by 100 twice, so
the mart reports 1/100th of it.

Nothing here is a scientific scenario and nothing here carries an answer key. The
canonical three-configuration demo world specified in `docs/DATA_WORLD_v0.md` is a
separate, shared piece of work and does not live in this module.
"""
from __future__ import annotations

from .database import ReadOnlyDatabase

# Orders per day, as the walkthrough trace observed them.
ORDERS_PER_DAY = (("2026-01-12", 298), ("2026-01-13", 301), ("2026-01-14", 297))
AMOUNT_CENTS = 100


def build_script() -> str:
    """The SQL that creates and fills the world. Deterministic: no clock, no randomness."""
    lines = [
        "CREATE TABLE orders (order_id TEXT PRIMARY KEY, order_date TEXT NOT NULL, "
        "amount_cents INTEGER NOT NULL);",
        "CREATE TABLE mart_daily (day TEXT PRIMARY KEY, revenue_usd REAL NOT NULL);",
    ]
    for day, count in ORDERS_PER_DAY:
        values = ", ".join(
            f"('{day.replace('-', '')}-{n:04d}', '{day}', {AMOUNT_CENTS})"
            for n in range(1, count + 1))
        lines.append(f"INSERT INTO orders VALUES {values};")
        # stg_orders.sql divides by 100 twice: cents -> dollars -> hundredths of a dollar.
        revenue = count * AMOUNT_CENTS / 100 / 100
        lines.append(f"INSERT INTO mart_daily VALUES ('{day}', {revenue});")
    return "\n".join(lines)


def open_walkthrough_world() -> ReadOnlyDatabase:
    return ReadOnlyDatabase.in_memory(build_script())
