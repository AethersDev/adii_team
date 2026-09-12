"""Tool execution and evidence grounding — the investigator's only door to the world.

    from adii.tools import build_sql_tools, open_walkthrough_world

    executor = build_sql_tools(open_walkthrough_world())
    result = executor.execute(ToolCall(call_id="c1", name="get_schema", arguments={}))

Everything the investigator sees comes back as a `ToolResult` from `ToolExecutor.execute`,
with a status it can act on: OK, DENIED, REJECTED, or ERROR.
"""
from .database import QueryResult, ReadOnlyDatabase, TableSchema
from .errors import Denied, Rejected
from .executor import ToolExecutor, canonical_json, evidence_id
from .schemas import Parameter, ToolSpec, validate_arguments
from .sql_tools import DEFAULT_MAX_ROWS, GET_SCHEMA, RUN_SQL, build_sql_tools
from .walkthrough_world import open_walkthrough_world

__all__ = [
    "DEFAULT_MAX_ROWS", "GET_SCHEMA", "RUN_SQL", "Denied", "Parameter", "QueryResult",
    "ReadOnlyDatabase", "Rejected", "TableSchema", "ToolExecutor", "ToolSpec",
    "build_sql_tools", "canonical_json", "evidence_id", "open_walkthrough_world",
    "validate_arguments",
]
