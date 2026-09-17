"""Applying a candidate patch to a frozen world, from scratch, every time.

CONFORMANCE C1: validation "rebuilds from frozen inputs" rather than mutating a
world the investigator already touched. `ReadOnlyDatabase` (tools/database.py)
enforces read-only at the authorizer, so there is no in-place "apply an UPDATE"
path even if one were tempting — the only way to get a post-patch world is to
build a new one from patched SQL text, the same way `walkthrough_world.py`
builds the original.

This module owns exactly that: substituting a patch's replacement expression
into the world's build script and constructing a brand-new `ReadOnlyDatabase`
from the result. It never touches the database the investigator's tools
used — that connection is never passed in, because nothing here accepts one.
"""
from __future__ import annotations

import ast
import operator

from adii.tools import ReadOnlyDatabase
from adii.tools.walkthrough_world import AMOUNT_CENTS, ORDERS_PER_DAY


class PatchRejected(Exception):
    """The patch could not be applied at all — malformed SQL, an unknown patch
    target, or anything else that means there is no world to check. Distinct
    from a patch that applies cleanly but produces the wrong result: that is
    `accepted=False` from a real check, not this exception."""


# A patch's revenue expression is arithmetic over `count` and numeric literals
# only — never `eval`. Each AST node type allowed is named explicitly; anything
# else (a call, a name other than `count`, a comprehension, ...) is refused
# before any code runs. Same posture tools/database.py takes with the SQL
# authorizer: an allowlist of what is safe, not a blocklist of what is dangerous.
_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub,
           ast.Mult: operator.mul, ast.Div: operator.truediv}
_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _eval_arithmetic(node: ast.AST, count: int) -> float:
    if isinstance(node, ast.Expression):
        return _eval_arithmetic(node.body, count)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id == "count":
        return count
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](
            _eval_arithmetic(node.left, count), _eval_arithmetic(node.right, count))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARYOPS:
        return _UNARYOPS[type(node.op)](_eval_arithmetic(node.operand, count))
    raise PatchRejected(f"patch expression is not plain arithmetic over count: {ast.dump(node)}")


def evaluate_patch_expression(expression: str, count: int) -> float:
    """Evaluate a patch's replacement expression for one day's revenue, safely:
    only `count`, numeric literals, and +-*/ reach this — no names, no calls,
    no attribute access. Raises `PatchRejected` for anything else."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as problem:
        raise PatchRejected(f"patch expression does not parse: {problem}") from None
    return _eval_arithmetic(tree, count)


def build_patched_script(patch: dict[str, str]) -> str:
    """Rebuild the walkthrough world's SQL text with a patch's replacement
    expression substituted for the known defect (`count * amount_cents / 100 /
    100`, the double-division `stg_orders.sql` bug the walkthrough incident is
    built around).

    `patch` is `InvestigationDecision.patch`: `{path: replacement_expression}`.
    Only one key is meaningful for this world today — the transform the
    walkthrough incident's answer key names, `stg_orders.sql` — and its value
    must be an arithmetic expression over `count` that computes one day's
    revenue. Anything else is a patch this world cannot apply, which is a
    rejection, never a silent no-op.
    """
    if "stg_orders.sql" not in patch:
        raise PatchRejected(
            "patch does not name stg_orders.sql — nothing in the walkthrough "
            "world's build script matches the transform this patch claims to fix")

    expression = patch["stg_orders.sql"].strip()
    if not expression:
        raise PatchRejected("patch for stg_orders.sql is empty")

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
        revenue = evaluate_patch_expression(expression, count)
        lines.append(f"INSERT INTO mart_daily VALUES ('{day}', {revenue});")
    return "\n".join(lines)


def apply_patch(patch: dict[str, str]) -> ReadOnlyDatabase:
    """The frozen world, rebuilt from scratch with `patch` applied. Raises
    `PatchRejected` when the patch cannot be applied at all; a patch that
    applies but is wrong is `validator.py`'s job to catch, not this one's."""
    script = build_patched_script(patch)
    return ReadOnlyDatabase.in_memory(script)
