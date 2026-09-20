"""Frozen operational schema declarations bound to logical database tables.

These declarations describe meaning SQLite cannot carry. They are investigator-visible
operational evidence, not inferred database facts and never evaluation or validation truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .packages import load_bundle, strict_json

DECLARED_SCHEMA_MAP_NAME = "declared_schema_map.json"
DECLARED_SCHEMA_SOURCE_DIR = "declared_schema_sources"


@dataclass(frozen=True)
class DeclaredSchema:
    """One exact source artifact and the operational object parsed from it."""

    source: str
    observation: dict[str, object]


def _parse_object(source: str, *, artifact: str) -> dict[str, object]:
    value = strict_json(source, artefact=f"declared schema {artifact!r}")
    if not isinstance(value, dict):
        raise ValueError(f"declared schema {artifact!r} must be a JSON object")
    source_name = value.get("source")
    version = value.get("schema_version")
    fields = value.get("fields")
    if not isinstance(source_name, str) or not source_name.strip():
        raise ValueError(f"declared schema {artifact!r} needs non-empty text source")
    if isinstance(version, bool) or not isinstance(version, (int, str)):
        raise ValueError(f"declared schema {artifact!r} needs text or integer schema_version")
    if not isinstance(fields, dict) or not all(
            isinstance(name, str) and name and isinstance(metadata, dict)
            for name, metadata in fields.items()):
        raise ValueError(
            f"declared schema {artifact!r} fields must map field names to objects")
    return value


def load_declared_schemas(folder: Path) -> dict[str, DeclaredSchema]:
    """The incident's declarations by the SQLite table each binds, source bytes preserved
    beside the parsed object; {} when it has none. Keys are table names, not logical ids."""
    bundle = load_bundle(folder, DECLARED_SCHEMA_MAP_NAME, DECLARED_SCHEMA_SOURCE_DIR, keys=None)
    if bundle is None:
        return {}
    mapping, files = bundle
    return {table: DeclaredSchema(source=files[filename],
                                  observation=_parse_object(files[filename], artifact=filename))
            for table, filename in mapping.items()}
