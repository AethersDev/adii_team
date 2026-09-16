"""Regenerate docs/current_status.md from the repository itself.

    python 02_src/scripts/sync_status.py

Nothing here is hand-maintained. What is built is derived by looking at the packages,
and the milestone states by reading the marks in build_plan.md. Those marks are the
single place a human edits.

Deliberately NOT here: anything that changes on every pull request. A test count would
make this page stale the moment somebody adds a test, and a status page that fails the
build for doing the right thing gets deleted within a month.

A status page maintained by hand is wrong within a fortnight and then actively misleads
the next person — which is worse than not having one. A test keeps this honest.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]
DOCS = SRC / "docs"
OUT = DOCS / "current_status.md"

PACKAGES = ("contracts", "investigator", "tools", "validation",
            "evaluation", "reporting", "runtime", "provider", "examples", "demo")


def implementation_lines(package: str) -> int:
    """Lines of real code, ignoring a package that is only a docstring."""
    total = 0
    for path in sorted((SRC / "adii" / package).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        body = [line for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#")]
        if path.name == "__init__.py" and len(body) <= 4:
            continue
        total += len(body)
    return total


def milestones() -> list[tuple[str, str, int, int]]:
    text = (DOCS / "build_plan.md").read_text(encoding="utf-8")
    found = []
    blocks = re.split(r"^## ", text, flags=re.M)[1:]
    for block in blocks:
        heading = block.splitlines()[0].strip()
        match = re.match(r"(M\d+) — (.*)", heading)
        if not match:
            continue
        name, rest = match.groups()
        state = "done" if rest.endswith("— DONE") else (
            "next" if rest.endswith("— NEXT") else "planned")
        title = re.sub(r" — (DONE|NEXT)$", "", rest)
        done = len(re.findall(r"^- \[x\]", block, re.M))
        total = len(re.findall(r"^- \[[ x]\]", block, re.M))
        found.append((f"{name} — {title}", state, done, total))
    return found


def render() -> str:
    built, scaffold = [], []
    for package in PACKAGES:
        lines = implementation_lines(package)
        (built if lines else scaffold).append((package, lines))

    rows = []
    for name, state, done, total in milestones():
        mark = {"done": "[x]", "next": "[>]", "planned": "[ ]"}[state]
        boxes = f"{done}/{total}" if total else "—"
        rows.append(f"    {mark}  {name:<42} {boxes}")

    return "\n".join([
        "# Current status",
        "",
        "**Generated. Do not edit.** `python 02_src/scripts/sync_status.py` rewrites it,",
        "and a test fails the build when it is stale. Milestone marks come from",
        "[build_plan.md](build_plan.md); what is built comes from looking at the code.",
        "",
        "## Milestones",
        "",
        "```text",
        *rows,
        "```",
        "",
        "## What exists",
        "",
        "```text",
        *[f"    {name:<16} {lines:>5} lines" for name, lines in built],
        "```",
        "",
        "## Scaffold only — a README and an empty package",
        "",
        "```text",
        *[f"    {name}" for name, _ in scaffold],
        "```" if scaffold else "    (none)",
        "",
        "## Verification",
        "",
        "```bash",
        "python 02_src/scripts/check_env.py",
        "pytest",
        "python -m ruff check 02_src",
        "python -m adii.examples.walkthrough",
        "python -m adii.demo",
        "```",
        "",
    ])


def main() -> int:
    text = render()
    current = OUT.read_text(encoding="utf-8") if OUT.is_file() else None
    if current == text:
        print("already current")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(SRC.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
