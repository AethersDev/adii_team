"""The tool layer: the only door between the investigator and the world.

Everything the investigator learns about a world it learns by asking a tool, and every tool
here can refuse. The database behind them is opened read-only and guarded by SQLite's own
authorizer, so a query that would write, attach or escape is denied before it runs.

Everything the investigator sees comes back as a `ToolResult` from `ToolExecutor.execute`,
with a status it can act on: OK, DENIED, REJECTED, or ERROR.
"""
from .change_history_tools import (
    CHANGE_HISTORY_MAP_NAME,
    CHANGE_HISTORY_SOURCE_DIR,
    ChangeHistory,
    change_history_observation,
    load_change_histories,
)
from .database import ReadOnlyDatabase
from .declared_schema_tools import (
    DECLARED_SCHEMA_MAP_NAME,
    DECLARED_SCHEMA_SOURCE_DIR,
    DeclaredSchema,
    load_declared_schemas,
)
from .errors import Denied, Rejected
from .executor import ToolExecutor, canonical_json, evidence_id
from .notice_tools import NOTICE_MAP_NAME, NOTICE_SOURCE_DIR, load_notice_sources
from .reconciliation_tools import (
    RECONCILIATION_MAP_NAME,
    RECONCILIATION_SOURCE_DIR,
    load_reconciliation_sources,
)
from .schemas import Parameter, ToolSpec, validate_arguments
from .sql_tools import GET_SCHEMA, RUN_SQL, build_sql_tools
from .transform_tools import TRANSFORM_MAP_NAME, TRANSFORM_SOURCE_DIR, load_transform_sources
from .walkthrough_world import open_walkthrough_world

# Every optional evidence bundle an incident folder may carry, as (map file, source
# directory): what the runtime copies into a run's folder and the archive attests.
EVIDENCE_BUNDLES = (
    (TRANSFORM_MAP_NAME, TRANSFORM_SOURCE_DIR),
    (NOTICE_MAP_NAME, NOTICE_SOURCE_DIR),
    (CHANGE_HISTORY_MAP_NAME, CHANGE_HISTORY_SOURCE_DIR),
    (RECONCILIATION_MAP_NAME, RECONCILIATION_SOURCE_DIR),
    (DECLARED_SCHEMA_MAP_NAME, DECLARED_SCHEMA_SOURCE_DIR),
)

__all__ = [
    "EVIDENCE_BUNDLES", "GET_SCHEMA", "RUN_SQL", "ChangeHistory", "DeclaredSchema", "Denied",
    "Parameter", "ReadOnlyDatabase", "Rejected", "ToolExecutor", "ToolSpec", "build_sql_tools",
    "canonical_json", "change_history_observation", "evidence_id", "load_change_histories",
    "load_declared_schemas", "load_notice_sources", "load_reconciliation_sources",
    "load_transform_sources", "open_walkthrough_world", "validate_arguments",
]
