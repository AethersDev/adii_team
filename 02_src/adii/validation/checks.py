"""The one kind of check a rebuilt world is put through: an invariant of the incident.

An invariant is two queries that must agree — one over the rebuilt world, one over the
frozen world's own inputs — named, and declared per incident in its oracle. It states what
must hold in a valid repaired world, never the patch or the repair that produces it: the
validator knows the invariant, not the answer.

CONFORMANCE C1(c): count alone is not enough. Invariants compare rows — identities and
values — so two worlds with the same number of rows and different ones do not agree.
"""
from __future__ import annotations

from dataclasses import dataclass

from adii.tools import ReadOnlyDatabase
from adii.tools.errors import Denied, Rejected

MAX_ROWS = 100_000


@dataclass(frozen=True)
class Invariant:
    name: str
    rebuilt: str         # over the rebuilt world
    frozen: str          # over the frozen world's inputs


@dataclass(frozen=True)
class CheckOutcome:
    passed: bool
    name: str
    detail: str


def check(invariant: Invariant, frozen: ReadOnlyDatabase,
          rebuilt: ReadOnlyDatabase) -> CheckOutcome:
    """Whether the rebuilt world agrees with the frozen one on this invariant, row for row.
    A query the rebuilt world cannot answer is a finding about the repair, not an error."""
    def rows(db: ReadOnlyDatabase, sql: str):
        result = db.query(sql, max_rows=MAX_ROWS)
        if result.truncated:
            raise Rejected(f"more than {MAX_ROWS} rows to compare")
        return result.rows
    want = rows(frozen, invariant.frozen)
    try:
        got = rows(rebuilt, invariant.rebuilt)
    except (Rejected, Denied) as unanswerable:          # the repair changed the world's shape
        return CheckOutcome(False, invariant.name, f"the rebuilt world cannot answer: "
                                                   f"{unanswerable}")
    if got == want:
        return CheckOutcome(True, invariant.name, f"{len(got)} row(s) agree")
    at = next((i for i, pair in enumerate(zip(got, want, strict=False)) if pair[0] != pair[1]),
              min(len(got), len(want)))
    return CheckOutcome(False, invariant.name,
                        f"{len(got)} row(s) rebuilt against {len(want)} expected; first "
                        f"difference at row {at}: rebuilt "
                        f"{got[at] if at < len(got) else 'nothing'}, expected "
                        f"{want[at] if at < len(want) else 'nothing'}")
