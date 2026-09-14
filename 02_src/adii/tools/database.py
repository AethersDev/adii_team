"""A SQLite database the investigator can only read.

CONFORMANCE B4: read-only is enforced by the database's authorizer, not by inspecting the
query text. SQLite consults the authorizer for every action a statement would perform
while it is being compiled — read a column, call a function, insert a row, attach another
file, run a pragma — and this module allows exactly four of them. A regex over the SQL is
a suggestion; this is a boundary. `ATTACH` matters most: it is the way a query reaches a
file the tool was never given.

CONFORMANCE B2: every result is bounded. Rows are capped, long cells are cut, and a query
that runs too long is interrupted and sent back as the model's mistake to narrow.

CONFORMANCE B3: the file path, when there is one, is runtime configuration handed to
`ReadOnlyDatabase.from_file` by whoever runs the incident. It is never a tool argument.

This module is the only reason this package imports `sqlite3`. Nothing else in `adii/`
may — `test_only_the_tool_layer_touches_the_outside_world` says so.
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .errors import Denied, Rejected

# The only actions a read needs. Everything else — INSERT, UPDATE, DELETE, CREATE,
# DROP, PRAGMA, ATTACH, TRANSACTION, ... — is denied, whatever the statement says it is.
ALLOWED_ACTIONS = frozenset({
    sqlite3.SQLITE_SELECT,      # a SELECT statement
    sqlite3.SQLITE_READ,        # reading a column of a table or view
    sqlite3.SQLITE_FUNCTION,    # calling a SQL function (count, upper, ...)
    sqlite3.SQLITE_RECURSIVE,   # a recursive common table expression
})

# Functions that are not reads even though they are functions.
FORBIDDEN_FUNCTIONS = frozenset({
    "load_extension", "readfile", "writefile", "edit", "fts3_tokenizer"})

# Authorizer action codes only. `sqlite3` reuses the same integers for other constant
# families (result codes, limits), so a lookup over every SQLITE_* name mislabels them.
_ACTION_NAMES = {
    getattr(sqlite3, f"SQLITE_{name}"): name for name in (
        "CREATE_INDEX", "CREATE_TABLE", "CREATE_TEMP_INDEX", "CREATE_TEMP_TABLE",
        "CREATE_TEMP_TRIGGER", "CREATE_TEMP_VIEW", "CREATE_TRIGGER", "CREATE_VIEW",
        "DELETE", "DROP_INDEX", "DROP_TABLE", "DROP_TEMP_INDEX", "DROP_TEMP_TABLE",
        "DROP_TEMP_TRIGGER", "DROP_TEMP_VIEW", "DROP_TRIGGER", "DROP_VIEW", "INSERT",
        "PRAGMA", "READ", "SELECT", "TRANSACTION", "UPDATE", "ATTACH", "DETACH",
        "ALTER_TABLE", "REINDEX", "ANALYZE", "CREATE_VTABLE", "DROP_VTABLE", "FUNCTION",
        "SAVEPOINT", "RECURSIVE")
    if hasattr(sqlite3, f"SQLITE_{name}")
}

PROGRESS_EVERY_N_INSTRUCTIONS = 10_000


@dataclass(frozen=True)
class QueryResult:
    columns: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...]
    truncated: bool


@dataclass(frozen=True)
class TableSchema:
    name: str
    columns: tuple[str, ...]
    ddl: str


class ReadOnlyDatabase:
    """Wraps a connection so that only reads can reach it. Build it, then hand it to the
    tools; the tools never see the connection."""

    def __init__(self, connection: sqlite3.Connection, *, max_progress_ticks: int = 500,
                 max_cell_chars: int = 500) -> None:
        if isinstance(max_progress_ticks, bool) or max_progress_ticks <= 0:
            raise ValueError("max_progress_ticks must be a positive int")
        if isinstance(max_cell_chars, bool) or max_cell_chars <= 0:
            raise ValueError("max_cell_chars must be a positive int")
        self._connection = connection
        self._max_progress_ticks = max_progress_ticks
        self._max_cell_chars = max_cell_chars
        self._denied: str | None = None
        self._ticks = 0
        self._interrupted = False
        connection.set_authorizer(self._authorize)
        connection.set_progress_handler(self._tick, PROGRESS_EVERY_N_INSTRUCTIONS)

    # -- construction --------------------------------------------------------------------

    @classmethod
    def in_memory(cls, build_script: str, **limits: int) -> ReadOnlyDatabase:
        """Run `build_script` once to populate an in-memory database, then lock it."""
        connection = sqlite3.connect(":memory:")
        connection.executescript(build_script)
        connection.commit()
        return cls(connection, **limits)

    @classmethod
    def from_file(cls, path: str | Path, **limits: int) -> ReadOnlyDatabase:
        """Open an existing database file read-only at the driver level too, so even a
        defect in the authorizer could not write it. `path` is configuration: it comes
        from the runtime, never from a `ToolCall`."""
        target = Path(path).resolve()
        if not target.is_file():
            raise FileNotFoundError(f"no database file at {target}")
        connection = sqlite3.connect(f"{target.as_uri()}?mode=ro", uri=True)
        return cls(connection, **limits)

    def close(self) -> None:
        self._connection.close()

    # -- the boundary --------------------------------------------------------------------

    def _authorize(self, action: int, arg1: object, arg2: object, db: object,
                   trigger: object) -> int:
        if action in ALLOWED_ACTIONS:
            if action == sqlite3.SQLITE_FUNCTION and str(arg2).lower() in FORBIDDEN_FUNCTIONS:
                self._denied = f"function {arg2}() is not available"
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        what = _ACTION_NAMES.get(action, f"action {action}")
        target = " ".join(str(a) for a in (arg1, arg2) if a is not None)
        self._denied = f"{what} {target}".strip() + " is not permitted: this database is read-only"
        return sqlite3.SQLITE_DENY

    def _tick(self) -> bool:
        self._ticks += 1
        if self._ticks > self._max_progress_ticks:
            self._interrupted = True
            return True  # non-zero aborts the statement
        return False

    # -- reads ---------------------------------------------------------------------------

    def query(self, sql: str, *, max_rows: int,
              parameters: tuple[object, ...] = ()) -> QueryResult:
        """Run one read-only statement. Raises `Denied` when the authorizer refused it and
        `Rejected` when the statement itself is the problem (syntax, unknown table, more
        than one statement, ran too long). `parameters` are for this package's own
        lookups; the model's tool passes none."""
        if isinstance(max_rows, bool) or max_rows <= 0:
            raise ValueError("max_rows must be a positive int")
        if not sql.strip():
            raise Rejected("the query is empty")
        self._denied, self._ticks, self._interrupted = None, 0, False
        try:
            cursor = self._connection.execute(sql, parameters)
            fetched = cursor.fetchmany(max_rows + 1)
        except sqlite3.ProgrammingError as problem:
            raise Rejected(f"one statement per call: {problem}") from None
        except sqlite3.DatabaseError as problem:
            if self._denied:
                raise Denied(self._denied) from None
            if self._interrupted:
                raise Rejected(
                    "the query exceeded its execution budget; narrow it with a WHERE "
                    "clause, fewer joins, or a LIMIT") from None
            raise Rejected(f"SQL error: {problem}") from None
        if cursor.description is None:
            raise Rejected("the statement returned no result set; only SELECT is useful here")
        columns = tuple(d[0] for d in cursor.description)
        rows = tuple(tuple(self._bound(v) for v in row) for row in fetched[:max_rows])
        return QueryResult(columns=columns, rows=rows, truncated=len(fetched) > max_rows)

    def tables(self) -> tuple[str, ...]:
        result = self.query(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name", max_rows=1_000)
        return tuple(str(row[0]) for row in result.rows)

    def schema(self, table: str) -> TableSchema:
        known = self.tables()
        if table not in known:
            raise Rejected(f"no such table {table!r}; known tables: {list(known)}")
        # The name was just checked against sqlite_master; quoting it is belt and braces.
        quoted = '"' + table.replace('"', '""') + '"'
        columns = self.query(f"SELECT * FROM {quoted} LIMIT 0", max_rows=1).columns
        ddl_rows = self.query("SELECT sql FROM sqlite_master WHERE name = ?",
                              max_rows=1, parameters=(table,))
        ddl = str(ddl_rows.rows[0][0]) if ddl_rows.rows and ddl_rows.rows[0][0] else ""
        return TableSchema(name=table, columns=columns, ddl=ddl)

    # -- bounding ------------------------------------------------------------------------

    def _bound(self, value: object) -> object:
        """A cell the model can see and JSON can carry."""
        if isinstance(value, bytes):
            return f"<blob {len(value)} bytes>"
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)  # 'inf' / 'nan' — strict JSON has no such literals
        if isinstance(value, str) and len(value) > self._max_cell_chars:
            return value[: self._max_cell_chars] + f"...[truncated, {len(value)} chars]"
        return value
