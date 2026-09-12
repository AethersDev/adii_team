"""What a tool advertises to the model, and the check that makes the advertisement true.

CONFORMANCE A1: a wrong-typed argument is a REJECTED result, not a crash. Binding checks
arity; it never checks types. So arguments are validated against the advertised schema
here, before any handler runs.

CONFORMANCE A3: a schema form the validator cannot enforce is refused at registration.
Four scalar types and `enum` are enforced; nested objects, arrays, and anything else are a
`ValueError` when the spec is built, not a constraint quietly waved through at run time.

CONFORMANCE B3: no tool takes a filesystem path. A parameter whose name says it is one is
refused at registration. That is a naming guard — the real defence is that no handler in
this package opens a caller-supplied path — but it catches the obvious case before review.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

ENFORCEABLE_TYPES = ("string", "integer", "number", "boolean")

PATH_LIKE_NAMES = frozenset({
    "path", "paths", "file", "files", "filename", "filepath", "file_path", "directory",
    "dir", "folder", "location", "uri", "url",
})


@dataclass(frozen=True)
class Parameter:
    """One argument a tool accepts. Scalar only, on purpose."""

    name: str
    type: str
    description: str = ""
    required: bool = True
    enum: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("parameter name must not be empty")
        if self.name.lower() in PATH_LIKE_NAMES:
            raise ValueError(
                f"parameter {self.name!r} looks like a filesystem path. No tool takes one: "
                "a tool that accepts a path can be pointed at the answer key.")
        if self.type not in ENFORCEABLE_TYPES:
            raise ValueError(
                f"parameter {self.name!r} has type {self.type!r}, which this validator cannot "
                f"enforce. Enforceable: {ENFORCEABLE_TYPES}. Refusing rather than advertising "
                "a constraint that would not be checked.")
        for value in self.enum:
            if not matches_type(self.type, value):
                raise ValueError(
                    f"enum value {value!r} of parameter {self.name!r} is not a {self.type}")


@dataclass(frozen=True)
class ToolSpec:
    """A tool's name, purpose, and parameters — the thing the loop advertises."""

    name: str
    description: str
    parameters: tuple[Parameter, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("tool name must not be empty")
        if not self.description.strip():
            raise ValueError(f"tool {self.name!r} must describe itself")
        names = [p.name for p in self.parameters]
        if len(names) != len(set(names)):
            raise ValueError(f"tool {self.name!r} declares a parameter twice: {names}")

    def to_json_schema(self) -> dict[str, object]:
        """The provider-neutral shape most model APIs accept for a tool definition."""
        properties: dict[str, object] = {}
        for p in self.parameters:
            prop: dict[str, object] = {"type": p.type}
            if p.description:
                prop["description"] = p.description
            if p.enum:
                prop["enum"] = list(p.enum)
            properties[p.name] = prop
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": [p.name for p in self.parameters if p.required],
                "additionalProperties": False,
            },
        }


def matches_type(type_name: str, value: object) -> bool:
    """JSON semantics, not Python's: a bool is not an integer and an int is a number."""
    if type_name == "boolean":
        return isinstance(value, bool)
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if type_name == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if type_name == "string":
        return isinstance(value, str)
    return False


def validate_arguments(spec: ToolSpec, arguments: object) -> list[str]:
    """Every way `arguments` fails `spec`, in words the model can act on. Empty means valid."""
    if not isinstance(arguments, Mapping):
        return [f"arguments must be an object, got {type(arguments).__name__}"]
    declared = {p.name: p for p in spec.parameters}
    problems: list[str] = []
    for name in arguments:
        if name not in declared:
            problems.append(
                f"unknown argument {name!r}; {spec.name} accepts {sorted(declared) or 'none'}")
    for p in spec.parameters:
        if p.name not in arguments:
            if p.required:
                problems.append(f"missing required argument {p.name!r}")
            continue
        value = arguments[p.name]
        if not matches_type(p.type, value):
            problems.append(
                f"argument {p.name!r} must be a {p.type}, got {type(value).__name__}")
        elif p.enum and value not in p.enum:
            problems.append(f"argument {p.name!r} must be one of {list(p.enum)}, got {value!r}")
    return problems
