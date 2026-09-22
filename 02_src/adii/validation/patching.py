"""Applying a candidate patch to a frozen world, from scratch, every time.

CONFORMANCE C1: validation "rebuilds from frozen inputs" rather than mutating a world the
investigator already touched. `ReadOnlyDatabase` (tools/database.py) enforces read-only at
the authorizer, so there is no in-place "apply an UPDATE" path even if one were tempting —
the only way to get a post-patch world is to build a new one from a build script, the same
way `walkthrough_world.py` builds the original.

This module owns exactly that. A REPAIR's patch is what the protocol tells the investigator
to send: the permitted path mapped to the file's full new contents. The walkthrough incident
permits one path, the staging transform `transforms/stg_orders.sql`: one statement over
`orders` that yields `amount_usd` per order. The rebuild runs the candidate transform as
`stg_orders` inside a fresh in-memory database and derives the mart from it as the world's
own pipeline does — revenue per day as the sum of `amount_usd` — under an instruction
budget, so a transform that never finishes is a refusal, not a hang. It never touches the
database the investigator's tools used: that connection is never passed in, because nothing
here accepts one.

A patch this world cannot apply — another path, an empty file, more than one statement, SQL
that does not run or does not yield what the mart needs — is `PatchRejected`, naming why: a
rejection, never a silent no-op. A patch that applies and is wrong is `checks.py`'s to catch.
"""
from __future__ import annotations

import re

from adii.tools import ReadOnlyDatabase
from adii.tools.walkthrough_world import AMOUNT_CENTS, ORDERS_PER_DAY

# The one path the walkthrough incident permits (01_data/walkthrough/incident.json): the
# staging transform. A patch names it exactly as the incident does.
TRANSFORM = "transforms/stg_orders.sql"
# The world's own derivation of the mart from the staging transform — frozen, never patched.
MART = ("CREATE TABLE mart_daily AS SELECT order_date AS day, SUM(amount_usd) AS revenue_usd "
        "FROM stg_orders GROUP BY order_date;")
# How long a candidate transform may run while the world is rebuilt: ticks of the tool
# layer's progress handler (10,000 SQLite instructions each). The frozen world builds in a
# handful; a transform still running at this many is refused, never waited for.
MAX_BUILD_TICKS = 2_000
# What a statement separator can hide in: a line comment, a block comment, a string literal.
# Struck out before the one-statement check, never from the SQL that runs.
_NOT_SQL = re.compile(r"--[^\n]*|/\*.*?\*/|'(?:[^']|'')*'", re.S)


class PatchRejected(Exception):
    """The patch could not be applied at all — the wrong path, an empty or multi-statement
    file, SQL the world refuses or that runs past its budget — so there is no world to check.
    Distinct from a patch that applies cleanly and produces the wrong result: that is
    `accepted=False` from a real check, not this exception."""


def transform_of(patch: dict[str, str]) -> str:
    """The candidate transform as one statement, or `PatchRejected` naming why not."""
    if set(patch) != {TRANSFORM}:
        raise PatchRejected(f"patch must name exactly {TRANSFORM}, the transform the incident "
                            f"permits; got {sorted(patch) or 'nothing'}")
    sql = patch[TRANSFORM].strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    bare = _NOT_SQL.sub("", sql).strip()
    if bare.endswith(";"):
        bare = bare[:-1].rstrip()
    if not bare:
        raise PatchRejected(f"patch for {TRANSFORM} is empty")
    if ";" in bare:
        raise PatchRejected(f"{TRANSFORM} must be one statement: the rebuild runs it as the "
                            "staging transform and nothing else")
    return sql


def build_patched_script(patch: dict[str, str]) -> str:
    """The walkthrough world's build script with the candidate transform in place of the
    defective one: the frozen orders, then `stg_orders` as the candidate defines it, then
    the mart as the world derives it."""
    transform = transform_of(patch)
    lines = ["CREATE TABLE orders (order_id TEXT PRIMARY KEY, order_date TEXT NOT NULL, "
             "amount_cents INTEGER NOT NULL);"]
    for day, count in ORDERS_PER_DAY:
        values = ", ".join(f"('{day.replace('-', '')}-{n:04d}', '{day}', {AMOUNT_CENTS})"
                           for n in range(1, count + 1))
        lines.append(f"INSERT INTO orders VALUES {values};")
    lines += [f"CREATE TABLE stg_orders AS {transform};", MART]
    return "\n".join(lines)


def apply_patch(patch: dict[str, str]) -> ReadOnlyDatabase:
    """The frozen world, rebuilt from scratch with `patch` applied. Raises `PatchRejected`
    when the patch cannot be applied at all — a transform SQLite refuses, one that yields
    no `amount_usd` or `order_date` for the mart to sum, or one still running at the
    budget; a patch that applies but is wrong is `validator.py`'s job to catch."""
    script = build_patched_script(patch)
    try:
        return ReadOnlyDatabase.in_memory(script, max_build_ticks=MAX_BUILD_TICKS)
    except ValueError as refused:          # the build SQLite would not run, in its words
        raise PatchRejected(f"the world does not rebuild with this transform: "
                            f"{refused}") from None
