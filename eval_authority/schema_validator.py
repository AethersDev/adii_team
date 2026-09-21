"""A minimal, dependency-free JSON Schema subset validator.

C5 requires the published schema to be checked against the validating
code by a test — not a full JSON Schema implementation. This module
implements exactly the keywords answer_key.schema.json actually uses
(type, required, additionalProperties, properties, enum, const,
minLength) and nothing more, in the standard library only, matching this
project's stated preference for no third-party runtime dependencies.

This is deliberately not a general JSON Schema engine: adding a keyword
here is only ever done because the published schema started using it.
"""
from __future__ import annotations


def _check_type(value, expected_type: str | list[str]) -> bool:
    types = expected_type if isinstance(expected_type, list) else [expected_type]
    checks = {
        "string": lambda v: isinstance(v, str),
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "boolean": lambda v: isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "null": lambda v: v is None,
    }
    return any(checks[t](value) for t in types)


def validate_against_schema(document: dict, schema: dict) -> list[str]:
    """Return a list of validation errors; empty means the document is valid.

    Supports exactly: type, required, additionalProperties, properties,
    enum, const, minLength — the keywords answer_key.schema.json uses.
    """
    errors = []

    if "type" in schema and schema["type"] == "object" and not isinstance(document, dict):
        return [f"document must be an object, got {type(document).__name__}"]

    for field in schema.get("required", []):
        if field not in document:
            errors.append(f"missing required field: {field!r}")

    if schema.get("additionalProperties") is False:
        allowed = set(schema.get("properties", {}))
        extra = set(document) - allowed
        for field in sorted(extra):
            errors.append(f"unexpected field not in schema: {field!r}")

    properties = schema.get("properties", {})
    for field, value in document.items():
        if field not in properties:
            continue
        field_schema = properties[field]
        errors.extend(_validate_field(field, value, field_schema))

    return errors


def _validate_field(field: str, value, field_schema: dict) -> list[str]:
    errors = []

    if "const" in field_schema and value != field_schema["const"]:
        errors.append(f"{field!r} must equal {field_schema['const']!r}, got {value!r}")

    if "type" in field_schema and not _check_type(value, field_schema["type"]):
        errors.append(f"{field!r} must be of type {field_schema['type']!r}, got {type(value).__name__}")

    if "enum" in field_schema and value not in field_schema["enum"]:
        errors.append(f"{field!r} must be one of {field_schema['enum']}, got {value!r}")

    if "minLength" in field_schema and isinstance(value, str) and len(value) < field_schema["minLength"]:
        errors.append(f"{field!r} must have length >= {field_schema['minLength']}, got {len(value)}")

    return errors


def is_valid(document: dict, schema: dict) -> bool:
    return not validate_against_schema(document, schema)
