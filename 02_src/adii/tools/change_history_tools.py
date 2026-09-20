"""Complete transform-change history by declared logical identifier.

The incident package preserves the original Markdown bytes.  This module parses that
artifact into the same four fields the historical investigator saw; it does not translate
filenames into current logical transform identifiers or otherwise enrich the evidence.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .executor import ToolExecutor
from .packages import LOGICAL_ID, load_bundle
from .schemas import Parameter, ToolSpec

DEFAULT_MAX_CHANGE_HISTORY_RECORDS = 100
CHANGE_HISTORY_MAP_NAME = "change_history_map.json"
CHANGE_HISTORY_SOURCE_DIR = "change_history_sources"
EXPECTED_HEADER = ("date", "file", "ticket", "change")
SEPARATOR = re.compile(r":?-{3,}:?\Z")
# The one date form the history promises. `date.fromisoformat` alone would also take
# 20260708 and 2026-W27-3, and the model would see three spellings of one field.
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


@dataclass(frozen=True)
class ChangeHistory:
    """One preserved source artifact and its deterministic model-visible records."""

    source: str
    changes: tuple[dict[str, str], ...]


def _cells(line: str) -> tuple[str, ...] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return tuple(cell.strip() for cell in stripped[1:-1].split("|"))


def parse_change_history(source: str, *, max_records: int) -> tuple[dict[str, str], ...]:
    """Parse one historical four-column Markdown table without semantic rewriting."""
    if isinstance(max_records, bool) or not isinstance(max_records, int) or max_records < 0:
        raise ValueError(f"max_records must be a non-negative int, got {max_records!r}")
    lines = source.splitlines()
    header_index = next(
        (index for index, line in enumerate(lines)
         if (cells := _cells(line)) is not None
         and tuple(cell.lower() for cell in cells) == EXPECTED_HEADER),
        None,
    )
    if header_index is None or header_index + 1 >= len(lines):
        raise ValueError("change history must contain a date/file/ticket/change Markdown table")
    separator = _cells(lines[header_index + 1])
    if separator is None or len(separator) != 4 \
            or not all(SEPARATOR.fullmatch(c) for c in separator):
        raise ValueError("change history table must have a four-column Markdown separator")

    changes: list[dict[str, str]] = []
    seen_tickets: set[str] = set()
    previous_date: date | None = None
    for line in lines[header_index + 2:]:
        if not line.strip():
            continue
        cells = _cells(line)
        if cells is None or len(cells) != 4 or any(not cell for cell in cells):
            raise ValueError(f"malformed change history row: {line!r}")
        raw_date, file_value, ticket, change = cells
        if not _DATE.fullmatch(raw_date):
            raise ValueError(f"change history date must be ISO YYYY-MM-DD: {raw_date!r}")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except ValueError as bad:
            raise ValueError(f"change history date is not a calendar date: {raw_date!r}") from bad
        if previous_date is not None and parsed_date > previous_date:
            raise ValueError("change history rows must be in newest-first order")
        if ticket in seen_tickets:
            raise ValueError(f"duplicate change history ticket {ticket!r}")
        seen_tickets.add(ticket)
        previous_date = parsed_date
        changes.append({
            "date": raw_date,
            "file": file_value,
            "ticket": ticket,
            "change": change,
        })
    if len(changes) > max_records:
        raise ValueError(
            f"change history has {len(changes)} records, exceeding max_records={max_records}; "
            "refusing a partial collection")
    return tuple(changes)


def load_change_histories(
        folder: Path, *, max_records: int = DEFAULT_MAX_CHANGE_HISTORY_RECORDS,
) -> dict[str, ChangeHistory]:
    """The incident's one change history, parsed, by logical id; {} when it has none."""
    bundle = load_bundle(folder, CHANGE_HISTORY_MAP_NAME, CHANGE_HISTORY_SOURCE_DIR)
    if bundle is None:
        return {}
    mapping, files = bundle
    if len(mapping) != 1:
        raise ValueError(f"{CHANGE_HISTORY_MAP_NAME} must declare exactly one history")
    [(history_id, filename)] = mapping.items()
    source = files[filename]
    return {history_id: ChangeHistory(
        source=source,
        changes=parse_change_history(source, max_records=max_records),
    )}


def change_history_observation(history_id: str, history: ChangeHistory) -> dict[str, object]:
    """The exact content exposed by the tool, before the executor adds evidence_id."""
    changes = [dict(change) for change in history.changes]
    return {
        "history_id": history_id,
        "ordering": "NEWEST_FIRST",
        "changes": changes,
        "count": len(changes),
        "truncated": False,
    }


def register_change_history_tool(
        executor: ToolExecutor, histories: Mapping[str, ChangeHistory],
) -> None:
    """Register the complete collection over a frozen copy of one parsed history."""
    if len(histories) != 1:
        raise ValueError("histories must declare exactly one transform change history")
    [(history_id, history)] = histories.items()
    if not isinstance(history_id, str) or not LOGICAL_ID.fullmatch(history_id):
        raise ValueError(f"history id {history_id!r} is not a logical identifier; "
                         "filesystem paths and traversal are forbidden")
    frozen = {history_id: ChangeHistory(history.source,
                                        tuple(dict(row) for row in history.changes))}
    spec = ToolSpec(
        name="get_change_history",
        description=(
            "Return the complete frozen transform change history in newest-first order. "
            "The argument is a logical identifier, never a filesystem path."),
        parameters=(Parameter(
            "history_id", "string", description="Declared logical history identifier.",
            enum=(history_id,),
        ),),
    )

    def get_change_history(history_id: str) -> dict[str, object]:
        return change_history_observation(history_id, frozen[history_id])

    executor.register(spec, get_change_history)
