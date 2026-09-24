"""The suite itself, hardened — inherited X4, X2 and D10 as tests.

Everything that is a test is collected; a hung test fails rather than blocks; every
third-party import is declared; and nothing we depend on is a name we do not own. Each of
these fails silently otherwise: a test that is never collected passes forever, a hung test
holds the pipeline instead of going red, a transitive import works until a neighbour drops
it, and a name resolved from a public index installs whatever squats on it.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "02_src"
TESTS = SRC / "tests"
IGNORED = {".git", ".venv", "node_modules", "__pycache__"}
BUILD_OUTPUT = (ROOT / "build", ROOT / "dist")       # a wheel build copies sources here

# The public-index packages this project has chosen, each pinned in requirements.txt.
# Adding a name here is a review decision, never a side effect of an import.
CHOSEN = {"pytest", "ruff", "pytest-timeout"}

# eval_authority's own modules import each other by bare name (from judge import ...),
# not as a package — see 02_src/tests/eval_authority/conftest.py. Internal code, not a
# public-index dependency, so it is excluded the same way "adii" itself is below.
EVAL_AUTHORITY_MODULES = {
    p.stem for p in (SRC / "tests" / "eval_authority").glob("*.py")
    if p.stem != "conftest"
}


def files_named_as_tests() -> set[Path]:
    """Every file on disk that pytest would treat as a test, wherever it is. Only the
    repository's own build output is ignored — never a name pytest happens to skip, or the
    check could not notice a test hidden in one."""
    found = {p.resolve() for p in ROOT.rglob("test_*.py")
             if not IGNORED & set(p.parts) and not any(b in p.parents for b in BUILD_OUTPUT)}
    return found - git_ignored(found)


def git_ignored(paths: set[Path]) -> set[Path]:
    """What .gitignore keeps out of the repository — a working folder, never shipped or
    tested. Outside a git checkout (an extracted submission ZIP) nothing is ignored."""
    try:
        answer = subprocess.run(["git", "check-ignore", "--stdin"], cwd=ROOT, text=True,
                                input="\n".join(str(p) for p in paths), capture_output=True)
    except FileNotFoundError:                     # no git on this machine
        return set()
    if answer.returncode not in (0, 1):           # 128: not a repository
        return set()
    return {Path(line).resolve() for line in answer.stdout.splitlines() if line}


def name(spec: str) -> str:
    """The package name in a requirement spec, normalised the way an index compares it."""
    return re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", spec).group().lower().replace("_", "-")


def declared() -> dict[str, set[str]]:
    """Dependency names by source: every pyproject table that names a package, and
    requirements.txt."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    specs = list(project["project"].get("dependencies", []))
    for extra in project["project"].get("optional-dependencies", {}).values():
        specs += extra
    for group in project.get("dependency-groups", {}).values():
        specs += [s for s in group if isinstance(s, str)]
    pins = [line.split("#")[0].strip()
            for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    return {"pyproject": {name(s) for s in specs},
            "requirements": {name(p) for p in pins if p and not p.startswith("-")}}


def test_every_test_file_lives_where_pytest_looks():
    """testpaths is 02_src/tests. A test anywhere else passes forever by never running."""
    outside = sorted(p.relative_to(ROOT).as_posix() for p in files_named_as_tests()
                     if TESTS not in p.parents)
    assert not outside, f"tests outside the configured test path, never collected: {outside}"


def test_every_test_file_is_collected_in_a_full_run(request):
    """Inside the test path a directory can still be unreachable — a name pytest does not
    recurse into, a conftest that ignores it. The full run knows what it collected."""
    config = request.config
    if config.getoption("file_or_dir") or config.getoption("keyword") \
            or config.getoption("markexpr"):
        pytest.skip("a partial run; the full run makes this assertion")
    collected = {item.path.resolve() for item in request.session.items}
    missing = sorted(p.relative_to(ROOT).as_posix()
                     for p in files_named_as_tests() - collected)
    assert not missing, f"test files on disk that this run did not collect: {missing}"


def test_every_third_party_import_is_declared():
    """Inherited X2: a module that arrives transitively disappears when a neighbour drops
    it, and the failure lands in code nobody changed. Imported directly, declared directly."""
    imported: set[str] = set()
    for path in SRC.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
    third_party = imported - sys.stdlib_module_names - {"adii"} - EVAL_AUTHORITY_MODULES
    undeclared = sorted(third_party - {n.replace("-", "_") for n in declared()["pyproject"]})
    assert not undeclared, f"imported but not declared in pyproject.toml: {undeclared}"


def test_every_dependency_is_a_name_we_chose_and_pinned():
    """Inherited D10: metadata that names a package we do not own is resolved from a public
    index by whoever installs without the lockfile. Every name is chosen here on purpose and
    pinned in requirements.txt, and nothing that sounds like ours comes from an index."""
    names = declared()
    assert names["pyproject"] == names["requirements"] == CHOSEN, (
        f"pyproject {sorted(names['pyproject'])}, requirements "
        f"{sorted(names['requirements'])}, chosen {sorted(CHOSEN)}")
    assert not [n for n in CHOSEN if n.startswith("adii")], "our own names never come from an index"


def test_a_hung_test_fails_instead_of_blocking(pytester):
    """Inherited X4: a per-test timeout, thread-based so it interrupts a native wait and
    exists on Windows. Run in a subprocess, because that is how the thread method ends a
    hung test — by ending the process, every stack printed."""
    pytester.makepyfile("import time\n\n\ndef test_hangs():\n    time.sleep(30)\n")
    started = time.monotonic()
    result = pytester.runpytest_subprocess("--timeout=1", "--timeout-method=thread",
                                           "-p", "no:cacheprovider")
    assert result.ret != 0
    assert time.monotonic() - started < 20, "the hung test was not interrupted"
    assert "Timeout" in result.stdout.str() + result.stderr.str()
