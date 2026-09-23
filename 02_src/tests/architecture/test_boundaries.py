"""Architecture fitness tests — the boundaries, made executable.

WHY THIS FILE EXISTS. Four people are writing code with coding agents, which means
implementations arrive faster than anyone can review them. An agent that has not been told
about this project will invent a reasonable-looking architecture of its own, and "reach
around the tool layer because it was simpler" is the single most likely way it does that.

architecture.md *asks* for these boundaries. This file *enforces* them. A rule that only
lives in prose is a rule an agent will cheerfully violate in a PR that passes every other
check.

If one of these fails, the fix is almost never to relax the test.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "adii"

# Packages that live in private repositories nobody here can check out. There is no
# adapter, no shared package, and no path on disk: an import of one of these is not a
# boundary to review later, it is code that builds on exactly one machine.
PRIVATE_PACKAGES = {"adii_env", "adii_eval", "adii_investigator"}

# Modules that reach the outside world directly. Only the tool layer may: the whole point
# of the tool layer is that the investigator sees data through a boundary that can refuse it.
OUTSIDE_WORLD = {"sqlite3", "subprocess", "socket", "urllib", "requests", "httpx",
                 "duckdb", "psycopg", "pymysql"}
# provider/ is the model boundary: the one place a model endpoint is spoken to, added by
# decision 2 in docs/plan_telemetry.md. The investigator still never imports it; the
# runtime builds a provider there and hands it in.
MAY_TOUCH_OUTSIDE = ("tools/", "examples/", "reporting/", "provider/")


def source_files() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def relative(path: Path) -> str:
    return path.relative_to(SRC).as_posix()


def imported_modules(path: Path) -> set[str]:
    """Top-level module names this file imports. Relative imports are ignored: they are
    internal structure, and the rules here are about crossing boundaries."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def calls_builtin_open(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
               and node.func.id == "open" for node in ast.walk(tree))


# ---------------------------------------------------------------------------

def test_contracts_depend_on_nothing_but_the_standard_library():
    """The contracts are what the whole system shares. The moment they depend on anything
    else, every component inherits that dependency and the shared vocabulary stops being
    free to import."""
    allowed = {"__future__", "dataclasses", "enum", "typing", "collections", "abc"}
    for path in (SRC / "contracts").rglob("*.py"):
        offending = imported_modules(path) - allowed
        assert not offending, (
            f"{relative(path)} imports {sorted(offending)}. Contracts must stay "
            "importable everywhere with no dependencies at all.")


def test_the_investigator_cannot_reach_the_judge():
    """The agent loop must not be able to see scoring or validation. Contestant and judge are
    different authorities; an investigator that can import the scorer can, eventually,
    be made to consult it."""
    for path in (SRC / "investigator").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("from ..evaluation", "from ..validation",
                          "adii.evaluation", "adii.validation"):
            assert forbidden not in text, (
                f"{relative(path)} reaches into {forbidden}. The investigator produces a "
                "decision and hands it over; it never learns how that decision is judged.")


@pytest.mark.parametrize("path", source_files(), ids=relative)
def test_only_the_tool_layer_touches_the_outside_world(path: Path):
    """Databases, subprocesses, and the network belong behind the tool layer.

    This is the rule a coding agent breaks first, because reading the CSV directly really
    is simpler. It is also the rule that, once broken, lets the agent read the answer key.
    """
    if relative(path).startswith(MAY_TOUCH_OUTSIDE):
        return
    offending = imported_modules(path) & OUTSIDE_WORLD
    assert not offending, (
        f"{relative(path)} imports {sorted(offending)}. Only the tool layer reaches the "
        "outside world — everything else goes through ToolCall/ToolResult.")


@pytest.mark.parametrize("path", source_files(), ids=relative)
def test_the_investigator_and_contracts_do_no_file_io(path: Path):
    """A tool that can open a file can open the answer key."""
    if not relative(path).startswith(("investigator/", "contracts/")):
        return
    assert not calls_builtin_open(path), (
        f"{relative(path)} calls open(). The agent loop has no filesystem — that is the point.")
    # open() is one route; Path.read_text, os and io are the others (the audit of 23 Sep)
    reaching = imported_modules(path) & {"pathlib", "os", "io", "shutil", "glob", "tempfile"}
    assert not reaching, (
        f"{relative(path)} imports {sorted(reaching)}. The agent loop has no filesystem.")


@pytest.mark.parametrize("path", source_files(), ids=relative)
def test_nothing_depends_on_a_private_repository(path: Path):
    """Knowledge transfer is one-way: findings cross into this repository, code does not.

    A previous implementation of ADII and its scored evaluation catalogue exist, and
    everything this project learned from them is in docs/inherited/. The repositories
    themselves are private. Importing one would make the build depend on a checkout that
    only one person has, and would quietly move our evaluation authority off-site.
    """
    offending = imported_modules(path) & PRIVATE_PACKAGES
    assert not offending, (
        f"{relative(path)} imports {sorted(offending)}. That package is in a private "
        "repository nobody else can check out — inherit the requirement, not the code.")


def test_inherited_results_are_labelled_as_prior_art():
    """The strongest evidence in docs/inherited/ was measured on a different system.

    Quoting 18/18 as though this codebase produced it would be the single most damaging
    thing anyone could do with these documents: it converts a real prior finding into a
    false claim about our work, and it would survive review because the number is true.
    """
    controls = SRC.parent / "docs" / "inherited" / "CONTROLS.md"
    text = controls.read_text(encoding="utf-8")
    assert "Whose numbers these are" in text, (
        "CONTROLS.md no longer says whose system produced its table. Prior-art results "
        "and our results are different claims and must never be reported as one.")


def test_the_inherited_knowledge_survives():
    """These carry defects already found and paid for. If one is deleted or hollowed out,
    the next implementation rediscovers them — and two of them can only be rediscovered by
    spending real money badly."""
    inherited = SRC.parent / "docs" / "inherited"
    for name in ("README.md", "CONFORMANCE.md", "AUTHORITY_LIFECYCLE.md", "CONTROLS.md"):
        path = inherited / name
        assert path.is_file(), f"docs/inherited/{name} is missing"
        assert len(path.read_text(encoding="utf-8").split()) > 150, (
            f"docs/inherited/{name} is too thin to transfer anything")
    conformance = (inherited / "CONFORMANCE.md").read_text(encoding="utf-8")
    for capability in ("Agent loop", "Tool execution", "Validation", "Telemetry"):
        assert capability in conformance, (
            f"CONFORMANCE.md no longer covers {capability}. The defects are grouped by "
            "what they constrain, never by who is assigned to it.")


def test_the_incident_world_still_has_to_pass_all_four_questions():
    """The world is part of the product argument, so nobody may quietly decide it alone.
    A world that is easy to build but cannot separate the three dispositions has failed,
    and that failure is invisible from inside the component that built it."""
    spec = SRC.parent / "docs" / "DATA_WORLD_v0.md"
    assert spec.is_file(), "docs/DATA_WORLD_v0.md is missing"
    text = spec.read_text(encoding="utf-8")
    for disposition in ("REPAIR", "NO_REPAIR", "ESCALATE"):
        assert disposition in text
    assert "Who decides" in text
    for question in ("Legibility", "Buildability", "Independence", "Reachability"):
        assert question in text, (
            f"DATA_WORLD_v0.md no longer makes the world answer for {question}")


def test_the_demo_is_never_imported_by_the_implementation():
    """The vision demo teaches the architecture. It must not quietly become the
    codebase the team inherits: it has fixture data where the real system has an agent, a
    tool layer, and a validator. One import from src/ and it stops being a demo."""
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        for reference in ("from demo", "import demo", "demo.fixtures"):
            assert reference not in text, (
                f"{relative(path)} references {reference!r}. The demo is an "
                "explanation, not an implementation — nothing in 02_src/adii may depend on it.")


def test_the_demo_backend_stays_dependency_free():
    """It runs on a laptop with nothing installed, which is most of why it is useful for
    onboarding. One import of a third-party package and that stops being true."""
    server = SRC / "demo" / "server.py"
    if not server.is_file():
        return
    allowed = {"__future__", "json", "http", "pathlib", "sys", "os", "typing", "datetime", "time",
               "threading",          # one lock: one run at a time in the process
               "hashlib", "tempfile"}    # a brought incident's id, and where it is staged
    offending = imported_modules(server) - allowed
    assert not offending, (
        f"demo/server.py imports {sorted(offending)}. Standard library only: the "
        "demo must run with nothing installed.")


def test_every_component_package_still_explains_itself():
    """A package README is the briefing a new teammate — or a new agent session — reads
    first. Anyone may work anywhere in this runtime, which only works if every part of it
    explains what it is for. If a package loses its README, the next session starts
    uninformed."""
    for package in ("investigator", "tools", "validation", "evaluation", "reporting"):
        readme = SRC / package / "README.md"
        assert readme.is_file(), f"02_src/adii/{package}/README.md is missing"
        assert len(readme.read_text(encoding="utf-8").split()) > 40, (
            f"02_src/adii/{package}/README.md is too thin to brief anyone")
