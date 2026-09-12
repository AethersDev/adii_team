"""The first two tools: `get_schema` and a read-only `run_sql`.

Each handler is a closure over a `ReadOnlyDatabase`, so the tool never holds a path, a
connection string, or anything the model could redirect. The model gets a table name or a
query, and gets back a bounded observation.

`run_sql` does not let the caller choose the row cap. A tool never returns more than the
harness decided it may — the model may narrow a query, never widen a result.
"""
from __future__ import annotations

from .database import ReadOnlyDatabase
from .executor import ToolExecutor
from .schemas import Parameter, ToolSpec

DEFAULT_MAX_ROWS = 50

GET_SCHEMA = ToolSpec(
    name="get_schema",
    description=(
        "Describe the warehouse. With no `table`, lists every table and its columns. With "
        "a `table`, returns that table's columns and its CREATE statement."),
    parameters=(
        Parameter("table", "string", required=False,
                  description="Name of one table to describe. Omit to list all tables."),
    ),
)

RUN_SQL = ToolSpec(
    name="run_sql",
    description=(
        "Run one read-only SQL SELECT against the warehouse and return at most "
        f"{DEFAULT_MAX_ROWS} rows. Writes, PRAGMA, and ATTACH are refused. Aggregate or "
        "add a LIMIT rather than reading whole tables."),
    parameters=(
        Parameter("query", "string", description="A single SELECT statement."),
    ),
)


def build_sql_tools(database: ReadOnlyDatabase, *, max_rows: int = DEFAULT_MAX_ROWS,
                    max_calls: int | None = None) -> ToolExecutor:
    """An executor with `get_schema` and `run_sql` registered against `database`."""
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows <= 0:
        raise ValueError(f"max_rows must be a positive int, got {max_rows!r}")

    def get_schema(table: str | None = None) -> dict[str, object]:
        if table is None:
            return {"tables": [
                {"name": name, "columns": list(database.schema(name).columns)}
                for name in database.tables()]}
        schema = database.schema(table)
        return {"table": schema.name, "columns": list(schema.columns), "ddl": schema.ddl}

    def run_sql(query: str) -> dict[str, object]:
        result = database.query(query, max_rows=max_rows)
        return {
            "columns": list(result.columns),
            "rows": [list(row) for row in result.rows],
            "row_count": len(result.rows),
            "truncated": result.truncated,
            "max_rows": max_rows,
        }

    executor = ToolExecutor(max_calls=max_calls)
    executor.register(GET_SCHEMA, get_schema)
    executor.register(RUN_SQL, run_sql)
    return executor
