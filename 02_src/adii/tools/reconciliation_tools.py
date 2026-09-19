"""Bounded raw-line windows over declared reconciliation sources.

The package loader owns filesystem access and hands the tool frozen text by logical ID.
The model can choose only an ID, offset, and bounded line count; it cannot search, filter,
name a path, or ask the tool to interpret operational statements in the source.

A line is a physical line: text between CR, LF or CRLF line ends. The same split serves the
per-line bound at load time and the window the model reads, so the two cannot disagree —
and a form feed or U+2028 inside a line stays inside it.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from .errors import Rejected
from .executor import ToolExecutor
from .packages import LOGICAL_ID, load_bundle
from .schemas import Parameter, ToolSpec

DEFAULT_RECONCILIATION_LIMIT = 200
MAX_RECONCILIATION_LIMIT = 200
DEFAULT_MAX_RECONCILIATION_BYTES = 1_000_000
DEFAULT_MAX_RECONCILIATION_LINE_BYTES = 20_000
RECONCILIATION_MAP_NAME = "reconciliation_map.json"
RECONCILIATION_SOURCE_DIR = "reconciliation_sources"
_LINE_END = re.compile(r"\r\n|\r|\n")


def physical_lines(source: str) -> tuple[str, ...]:
    """The source's lines by its line ends only, a final line end closing the last line."""
    lines = _LINE_END.split(source)
    if lines and lines[-1] == "":
        lines.pop()
    return tuple(lines)


def _validate_source(
        reconciliation_id: str,
        source: str,
        *,
        max_source_bytes: int,
        max_line_bytes: int,
) -> None:
    if not isinstance(reconciliation_id, str) or not LOGICAL_ID.fullmatch(reconciliation_id):
        raise ValueError(
            f"reconciliation id {reconciliation_id!r} is not a logical identifier; "
            "filesystem paths and traversal are forbidden")
    if not isinstance(source, str):
        raise ValueError(f"source for reconciliation {reconciliation_id!r} must be text")
    size = len(source.encode("utf-8"))
    if size > max_source_bytes:
        raise ValueError(
            f"source for reconciliation {reconciliation_id!r} has {size} bytes, exceeding "
            f"max_source_bytes={max_source_bytes}")
    for number, line in enumerate(physical_lines(source), start=1):
        line_size = len(line.encode("utf-8"))
        if line_size > max_line_bytes:
            raise ValueError(
                f"line {number} of reconciliation {reconciliation_id!r} has "
                f"{line_size} bytes, exceeding max_line_bytes={max_line_bytes}")


def _validate_bounds(max_source_bytes: int, max_line_bytes: int) -> None:
    for name, value in (
        ("max_source_bytes", max_source_bytes),
        ("max_line_bytes", max_line_bytes),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive int, got {value!r}")


def load_reconciliation_sources(
        folder: Path,
        *,
        max_source_bytes: int = DEFAULT_MAX_RECONCILIATION_BYTES,
        max_line_bytes: int = DEFAULT_MAX_RECONCILIATION_LINE_BYTES,
) -> dict[str, str]:
    """The incident's reconciliation bundle as logical id → source, each within the
    bounds; {} when it has none."""
    _validate_bounds(max_source_bytes, max_line_bytes)
    bundle = load_bundle(folder, RECONCILIATION_MAP_NAME, RECONCILIATION_SOURCE_DIR)
    if bundle is None:
        return {}
    mapping, files = bundle
    sources: dict[str, str] = {}
    for reconciliation_id, filename in mapping.items():
        _validate_source(
            reconciliation_id,
            files[filename],
            max_source_bytes=max_source_bytes,
            max_line_bytes=max_line_bytes,
        )
        sources[reconciliation_id] = files[filename]
    return sources


def register_reconciliation_tool(
        executor: ToolExecutor,
        reconciliation_sources: Mapping[str, str],
        *,
        max_source_bytes: int = DEFAULT_MAX_RECONCILIATION_BYTES,
        max_line_bytes: int = DEFAULT_MAX_RECONCILIATION_LINE_BYTES,
) -> None:
    """Register raw ordered line windows over a frozen source mapping."""
    _validate_bounds(max_source_bytes, max_line_bytes)
    if not reconciliation_sources:
        raise ValueError("reconciliation_sources must declare at least one source")
    frozen: dict[str, tuple[str, ...]] = {}
    for reconciliation_id, source in reconciliation_sources.items():
        _validate_source(
            reconciliation_id,
            source,
            max_source_bytes=max_source_bytes,
            max_line_bytes=max_line_bytes,
        )
        frozen[reconciliation_id] = physical_lines(source)

    reconciliation_ids = tuple(sorted(frozen))
    spec = ToolSpec(
        name="read_reconciliation",
        description=(
            "Return one bounded raw-line window from a declared reconciliation source in "
            "physical source order. No search, date predicate, or field filter is applied."),
        parameters=(
            Parameter(
                "reconciliation_id", "string",
                description="Declared logical reconciliation identifier.",
                enum=reconciliation_ids,
            ),
            Parameter(
                "offset", "integer", required=False,
                description="Zero-based source-line offset; default 0.",
            ),
            Parameter(
                "limit", "integer", required=False,
                description=(
                    "Number of lines to return; default and maximum "
                    f"{MAX_RECONCILIATION_LIMIT}."),
            ),
        ),
    )

    def read_reconciliation(
            reconciliation_id: str,
            offset: int = 0,
            limit: int = DEFAULT_RECONCILIATION_LIMIT,
    ) -> dict[str, object]:
        if offset < 0:
            raise Rejected("offset must be non-negative")
        if limit <= 0 or limit > MAX_RECONCILIATION_LIMIT:
            raise Rejected(
                f"limit must be between 1 and {MAX_RECONCILIATION_LIMIT}, got {limit}")
        all_lines = frozen[reconciliation_id]
        lines = list(all_lines[offset:offset + limit])
        next_offset = offset + len(lines)
        truncated = next_offset < len(all_lines)
        return {
            "reconciliation_id": reconciliation_id,
            "offset": offset,
            "total_lines": len(all_lines),
            "returned": len(lines),
            "lines": lines,
            "truncated": truncated,
            "next_offset": next_offset if truncated else None,
        }

    executor.register(spec, read_reconciliation)
