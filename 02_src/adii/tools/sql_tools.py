"""The first two tools: `get_schema` and a read-only `run_sql`.

Each handler is a closure over a `ReadOnlyDatabase`, so the tool never holds a path, a
connection string, or anything the model could redirect. The model gets a table name or a
query, and gets back a bounded observation.

`run_sql` does not let the caller choose the row cap. A tool never returns more than the
harness decided it may — the model may narrow a query, never widen a result.
"""
from __future__ import annotations

import json
from collections.abc import Mapping

from .change_history_tools import ChangeHistory, register_change_history_tool
from .database import ReadOnlyDatabase
from .declared_schema_tools import DeclaredSchema
from .executor import ToolExecutor, canonical_json
from .notice_tools import DEFAULT_MAX_NOTICE_CHARS, register_notice_tool
from .reconciliation_tools import (
    DEFAULT_MAX_RECONCILIATION_BYTES,
    DEFAULT_MAX_RECONCILIATION_LINE_BYTES,
    register_reconciliation_tool,
)
from .schemas import Parameter, ToolSpec
from .transform_tools import DEFAULT_MAX_TRANSFORM_CHARS, register_transform_tool

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
                    max_calls: int | None = None,
                    declared_schemas: Mapping[str, DeclaredSchema] | None = None,
                    transform_sources: Mapping[str, str] | None = None,
                    max_transform_chars: int = DEFAULT_MAX_TRANSFORM_CHARS,
                    notice_sources: Mapping[str, str] | None = None,
                    max_notice_chars: int = DEFAULT_MAX_NOTICE_CHARS,
                    change_histories: Mapping[str, ChangeHistory] | None = None,
                    reconciliation_sources: Mapping[str, str] | None = None,
                    max_reconciliation_bytes: int = DEFAULT_MAX_RECONCILIATION_BYTES,
                    max_reconciliation_line_bytes: int = DEFAULT_MAX_RECONCILIATION_LINE_BYTES,
                    ) -> ToolExecutor:
    """Build the read-only SQL surface, optionally with frozen transform source access."""
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows <= 0:
        raise ValueError(f"max_rows must be a positive int, got {max_rows!r}")
    frozen_declared: dict[str, dict[str, object]] = {}
    if declared_schemas is not None:
        unknown = set(declared_schemas) - set(database.tables())
        if unknown:
            raise ValueError(
                f"declared schemas name unknown tables: {', '.join(sorted(unknown))}")
        frozen_declared = {
            table: json.loads(canonical_json(declaration.observation))
            for table, declaration in declared_schemas.items()
        }

    def get_schema(table: str | None = None) -> dict[str, object]:
        if table is None:
            return {"tables": [
                {"name": name, "columns": list(database.schema(name).columns)}
                for name in database.tables()]}
        schema = database.schema(table)
        result: dict[str, object] = {
            "table": schema.name, "columns": list(schema.columns), "ddl": schema.ddl}
        if table in frozen_declared:
            result["declared_schema"] = frozen_declared[table]
        return result

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
    if transform_sources is not None:
        register_transform_tool(
            executor, transform_sources, max_chars=max_transform_chars)
    if notice_sources is not None:
        register_notice_tool(executor, notice_sources, max_chars=max_notice_chars)
    if change_histories is not None:
        register_change_history_tool(executor, change_histories)
    if reconciliation_sources is not None:
        register_reconciliation_tool(
            executor,
            reconciliation_sources,
            max_source_bytes=max_reconciliation_bytes,
            max_line_bytes=max_reconciliation_line_bytes,
        )
    return executor
