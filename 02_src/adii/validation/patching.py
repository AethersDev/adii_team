"""Applying a candidate patch to a frozen world, from scratch, every time.

requirement C1: validation rebuilds from frozen inputs rather than mutating a world the
investigator already touched. `ReadOnlyDatabase` (tools/database.py) enforces read-only at
the authorizer, so the only way to a post-patch world is a new one built from a script.

The script is the incident's own: its frozen world, then its pipeline — the derived tables
the incident declares, in order, each dropped and derived again, from the incident's frozen
transform where the pipeline names one and from the pipeline's own SQL where it does not.
A patch is what the protocol tells a model to send: a transform's path,
`transforms/<id>.sql`, mapped to the file's full new contents, and it may replace only a
transform the pipeline declares. Nothing here knows any incident; the pipeline is data, from
the incident's oracle (`validator.py`).

The rebuild runs under an instruction budget, so a transform that never finishes is a
refusal, not a hang. A patch this world cannot apply — a path the pipeline does not derive,
an empty file, more than one statement, SQL that does not run — is `PatchRejected`, naming
why: a rejection, never a silent no-op. A patch that applies and is wrong is the oracle's
to catch.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from adii.tools import ReadOnlyDatabase

# A rebuild may cost twice what building the frozen world cost, plus this floor, in ticks of
# the tool layer's progress handler (10,000 SQLite instructions each): the world again, and as
# much again for a candidate that derives more of it than the broken transform did — so a world
# of millions of rows rebuilds, and a runaway is still cut at a bound that grows with the world.
MAX_BUILD_TICKS = 2_000
# What a statement separator can hide in: a line comment, a block comment, a string literal.
# Struck out before the one-statement check, never from the SQL that runs.
_NOT_SQL = re.compile(r"--[^\n]*|/\*.*?\*/|'(?:[^']|'')*'", re.S)


def path_of(transform: str) -> str:
    """The path a model names a transform by, as the incident permits and serves it."""
    return f"transforms/{transform}.sql"


class PatchRejected(Exception):
    """The patch could not be applied at all, so there is no world to check. Distinct from
    a patch that applies cleanly and produces the wrong world: that is the oracle's finding."""


@dataclass(frozen=True)
class Step:
    """One derived table: from a frozen transform the patch may replace, or from the
    pipeline's own SQL, which no patch reaches."""
    table: str
    transform: str | None = None
    sql: str | None = None


def one_statement(name: str, text: str) -> str:
    """`text` as one SQL statement, or `PatchRejected` naming why not."""
    sql = text.strip()
    if sql.endswith(";"):
        sql = sql[:-1].rstrip()
    bare = _NOT_SQL.sub("", sql).strip()
    if bare.endswith(";"):
        bare = bare[:-1].rstrip()
    if not bare:
        raise PatchRejected(f"{name} is empty")
    if ";" in bare:
        raise PatchRejected(f"{name} must be one statement: the rebuild runs it as its "
                            "pipeline step and nothing else")
    return sql


def rebuild_script(world: str, pipeline: tuple[Step, ...], transforms: dict[str, str],
                   patch: dict[str, str]) -> str:
    """The frozen world, then every pipeline table derived again — from the patch where it
    replaces a transform, from the frozen transform or the step's own SQL otherwise."""
    patchable = {path_of(s.transform) for s in pipeline if s.transform}
    if not patch or set(patch) - patchable:
        raise PatchRejected(f"a patch replaces transforms the pipeline derives, by path — "
                            f"{sorted(patchable)}; got {sorted(patch) or 'nothing'}")
    derived = []
    for step in pipeline:
        if step.transform is None:
            derived.append((step.table, step.sql))
            continue
        path = path_of(step.transform)
        source = patch[path] if path in patch else transforms[step.transform]
        derived.append((step.table, one_statement(path, source)))
    return "\n".join([world, *(f'DROP TABLE IF EXISTS "{t}";' for t, _ in reversed(derived)),
                      *(f'CREATE TABLE "{t}" AS {sql};' for t, sql in derived)])


def apply_patch(world: str, pipeline: tuple[Step, ...], transforms: dict[str, str],
                patch: dict[str, str], world_ticks: int = 0) -> ReadOnlyDatabase:
    """The frozen world, rebuilt from scratch with `patch` applied, or `PatchRejected`.
    `world_ticks` is what building the frozen world cost; the rebuild may cost twice that
    plus MAX_BUILD_TICKS."""
    script = rebuild_script(world, pipeline, transforms, patch)
    try:
        return ReadOnlyDatabase.in_memory(script, max_build_ticks=2 * world_ticks + MAX_BUILD_TICKS)
    except ValueError as refused:          # the build SQLite would not run, in its words
        raise PatchRejected(f"the world does not rebuild with this patch: {refused}") from None
