"""One closed evidence bundle — the shape every optional evidence package shares.

A bundle is a map file beside a directory: the map binds logical identifiers to package-
local filenames, the directory holds exactly those files. Transforms, notices, the change
history, reconciliation sources and declared schemas are all this shape, so the rules live
once: the map is strict JSON (no duplicate keys, no NaN or Infinity), every filename is one
package-local name, every declared file is present and nothing undeclared is, nothing is a
symbolic link, and every file's bytes are read as UTF-8 exactly as they are. An absent
bundle is None; anything else that is not a bundle is a ValueError naming the reason.

Pure loading: this module knows no tool. Each kind of evidence turns the (mapping, files)
pair into its own frozen observation.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LOGICAL_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,127}\Z")
FILENAME = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")


def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _not_json(value: str) -> object:
    raise ValueError(f"non-finite JSON value {value!r}")


def strict_json(text: str, *, artefact: str) -> object:
    """JSON as the archive can hold it: one value per key, no NaN or Infinity."""
    try:
        return json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_not_json)
    except json.JSONDecodeError as bad:
        raise ValueError(f"{artefact} is not valid JSON: {bad.msg}") from bad


def load_bundle(folder: Path, map_name: str, dir_name: str, *,
                keys: re.Pattern[str] | None = LOGICAL_ID,
                ) -> tuple[dict[str, str], dict[str, str]] | None:
    """`folder/map_name` and `folder/dir_name/` as (mapping, files): the map as declared,
    key → filename, and each file's text by filename. None when neither exists. `keys`
    is the shape a key must have; None accepts any non-empty text (a table name)."""
    map_path, source_dir = folder / map_name, folder / dir_name
    if not any((map_path.exists(), map_path.is_symlink(), source_dir.exists(),
                source_dir.is_symlink())):
        return None
    if not map_path.is_file() or map_path.is_symlink() or not source_dir.is_dir() \
            or source_dir.is_symlink():
        raise ValueError(f"{map_name} must be a regular file beside a {dir_name}/ directory")
    mapping = strict_json(map_path.read_bytes().decode("utf-8"), artefact=map_name)
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError(f"{map_name} must be a non-empty object")
    for key, filename in mapping.items():
        if not key or (keys is not None and not keys.fullmatch(key)):
            raise ValueError(f"{map_name}: {key!r} is not a logical identifier; "
                             "filesystem paths and traversal are forbidden")
        if not isinstance(filename, str) or not FILENAME.fullmatch(filename):
            raise ValueError(f"{map_name}: {filename!r} is not one package-local filename")
    filenames = list(mapping.values())
    if len(filenames) != len(set(filenames)):
        raise ValueError(f"{map_name} must bind each file exactly once")
    entries = tuple(source_dir.iterdir())
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise ValueError(f"{dir_name}/ may contain regular files only")
    present, declared = {entry.name for entry in entries}, set(filenames)
    if present != declared:
        raise ValueError(f"{dir_name}/ differs from {map_name}: "
                         f"missing={sorted(declared - present)}, "
                         f"unbound={sorted(present - declared)}")
    files = {name: (source_dir / name).read_bytes().decode("utf-8") for name in filenames}
    return mapping, files
