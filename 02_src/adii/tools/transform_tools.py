"""Read-only transform source by declared logical identifier.

The harness supplies frozen source text. The handler never receives or opens a path, so
the investigator cannot redirect it toward evaluation material. Every configured source
must fit the observation bound in full: a partial transform would recreate the
read-before-repair defect while looking like evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .executor import ToolExecutor
from .packages import LOGICAL_ID, load_bundle
from .schemas import Parameter, ToolSpec

DEFAULT_MAX_TRANSFORM_CHARS = 100_000
TRANSFORM_MAP_NAME = "transform_map.json"
TRANSFORM_SOURCE_DIR = "transform_sources"


def load_transform_sources(folder: Path) -> dict[str, str]:
    """The incident's transform bundle as logical id → source text; {} when it has none.
    The bundle is closed (see `packages.load_bundle`); no filename leaves this function."""
    bundle = load_bundle(folder, TRANSFORM_MAP_NAME, TRANSFORM_SOURCE_DIR)
    if bundle is None:
        return {}
    mapping, files = bundle
    return {transform_id: files[filename] for transform_id, filename in mapping.items()}


def register_transform_tool(
        executor: ToolExecutor,
        transform_sources: Mapping[str, str],
        *,
        max_chars: int = DEFAULT_MAX_TRANSFORM_CHARS,
) -> None:
    """Register one bounded source reader over a frozen copy of ``transform_sources``."""
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars <= 0:
        raise ValueError(f"max_chars must be a positive int, got {max_chars!r}")
    if not transform_sources:
        raise ValueError("transform_sources must declare at least one logical transform")

    frozen: dict[str, str] = {}
    for transform_id, source in transform_sources.items():
        if not isinstance(transform_id, str) or not LOGICAL_ID.fullmatch(transform_id):
            raise ValueError(
                f"transform id {transform_id!r} is not a logical identifier; "
                "filesystem paths and traversal are forbidden")
        if not isinstance(source, str):
            raise ValueError(f"source for transform {transform_id!r} must be text")
        if len(source) > max_chars:
            raise ValueError(
                f"source for transform {transform_id!r} has {len(source)} characters, "
                f"exceeding max_chars={max_chars}; refusing a partial transform")
        frozen[transform_id] = source

    transform_ids = tuple(sorted(frozen))
    spec = ToolSpec(
        name="get_transform",
        description=(
            "Return the complete frozen source of one declared transform. The argument is "
            "a logical identifier, never a filesystem path."),
        parameters=(Parameter(
            "transform_id",
            "string",
            description="Declared logical transform identifier.",
            enum=transform_ids,
        ),),
    )

    def get_transform(transform_id: str) -> dict[str, object]:
        source = frozen[transform_id]
        return {
            "transform_id": transform_id,
            "source": source,
            "characters": len(source),
            "max_chars": max_chars,
            "truncated": False,
        }

    executor.register(spec, get_transform)
