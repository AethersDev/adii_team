"""Read-only operational notices by declared logical identifier.

Notices are evidence supplied by the incident harness, never evaluator truth. The model
can discover and request declared notice IDs, but it cannot supply a filename or redirect
the reader to another part of the incident package.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .executor import ToolExecutor
from .packages import LOGICAL_ID, load_bundle
from .schemas import Parameter, ToolSpec

DEFAULT_MAX_NOTICE_CHARS = 50_000
NOTICE_MAP_NAME = "notice_map.json"
NOTICE_SOURCE_DIR = "notice_sources"


def load_notice_sources(folder: Path) -> dict[str, str]:
    """The incident's notice bundle as logical id → content; {} when it has none."""
    bundle = load_bundle(folder, NOTICE_MAP_NAME, NOTICE_SOURCE_DIR)
    if bundle is None:
        return {}
    mapping, files = bundle
    return {notice_id: files[filename] for notice_id, filename in mapping.items()}


def register_notice_tool(
        executor: ToolExecutor,
        notice_sources: Mapping[str, str],
        *,
        max_chars: int = DEFAULT_MAX_NOTICE_CHARS,
) -> None:
    """Register one bounded notice reader over a frozen copy of ``notice_sources``."""
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
        raise ValueError(f"max_chars must be a positive int, got {max_chars!r}")
    if not notice_sources:
        raise ValueError("notice_sources must declare at least one operational notice")

    frozen: dict[str, str] = {}
    for notice_id, content in notice_sources.items():
        if not isinstance(notice_id, str) or not LOGICAL_ID.fullmatch(notice_id):
            raise ValueError(
                f"notice id {notice_id!r} is not a logical identifier; "
                "filesystem paths and traversal are forbidden")
        if not isinstance(content, str):
            raise ValueError(f"content for notice {notice_id!r} must be text")
        if len(content) > max_chars:
            raise ValueError(
                f"content for notice {notice_id!r} has {len(content)} characters, "
                f"exceeding max_chars={max_chars}; refusing a partial notice")
        frozen[notice_id] = content

    notice_ids = tuple(sorted(frozen))
    spec = ToolSpec(
        name="get_notice",
        description=(
            "Return the complete frozen content of one declared operational notice. The "
            "argument is a logical identifier, never a filesystem path."),
        parameters=(Parameter(
            "notice_id",
            "string",
            description="Declared logical operational-notice identifier.",
            enum=notice_ids,
        ),),
    )

    def get_notice(notice_id: str) -> dict[str, object]:
        content = frozen[notice_id]
        return {
            "notice_id": notice_id,
            "content": content,
            "characters": len(content),
            "max_chars": max_chars,
            "truncated": False,
        }

    executor.register(spec, get_notice)
