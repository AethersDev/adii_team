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


def changes_the_world(tables: tuple[str, ...], frozen: ReadOnlyDatabase,
                      rebuilt: ReadOnlyDatabase) -> CheckOutcome:
    """A repair repairs something: at least one derived table differs from the frozen world.
    A patch that rebuilds the world exactly as it was is no repair, however valid its SQL —
    and this asks nothing about the incident, only whether the world moved. Compared by
    streamed fingerprint, so a table of millions of rows is never held."""
    kept = set(frozen.tables())          # a derived table the frozen world never built has
    moved = [t for t in tables if t in kept and                                   # no before
             frozen.fingerprint(f'SELECT * FROM "{t}"') != rebuilt.fingerprint(
                 f'SELECT * FROM "{t}"')]
    if moved:
        return CheckOutcome(True, "changes_the_world", f"the repair changes {', '.join(moved)}")
    return CheckOutcome(False, "changes_the_world", "the rebuilt world is the frozen world, "
                        "table for table: the patch changes nothing")


def check(invariant: Invariant, frozen: ReadOnlyDatabase,
          rebuilt: ReadOnlyDatabase) -> CheckOutcome:
    """Whether the rebuilt world agrees with the frozen one on this invariant, row for row.
    Compared by streamed fingerprint, so it holds at any size; where the two disagree and fit
    in memory, the first differing row is named. A query the rebuilt world cannot answer is a
    finding about the repair, not an error."""
    want = frozen.fingerprint(invariant.frozen)
    try:
        got = rebuilt.fingerprint(invariant.rebuilt)
    except (Rejected, Denied) as unanswerable:          # the repair changed the world's shape
        return CheckOutcome(False, invariant.name, f"the rebuilt world cannot answer: "
                                                   f"{unanswerable}")
    if got == want:
        return CheckOutcome(True, invariant.name, f"{got[0]} row(s) agree")
    detail = f"{got[0]} row(s) rebuilt against {want[0]} expected"
    if max(got[0], want[0]) <= MAX_ROWS:
        g = rebuilt.query(invariant.rebuilt, max_rows=MAX_ROWS).rows
        w = frozen.query(invariant.frozen, max_rows=MAX_ROWS).rows
        at = next((i for i, pair in enumerate(zip(g, w, strict=False)) if pair[0] != pair[1]),
                  min(len(g), len(w)))
        detail += (f"; first difference at row {at}: rebuilt {g[at] if at < len(g) else 'nothing'}"
                   f", expected {w[at] if at < len(w) else 'nothing'}")
    else:
        detail += "; their rows differ"
    return CheckOutcome(False, invariant.name, detail)
