"""Every internal link in the documentation resolves.

The repository moved to the submission layout in one pass, and a blind path rewrite is
exactly the kind of change that leaves a link pointing at 02_src/docs/02_src/docs/. A
newcomer following a dead link learns that the documentation is not maintained, which is
the one lesson this repo cannot afford to teach on day one.

Anchors are not checked. Existence is.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]

LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")

SKIP_PREFIXES = ("http://", "https://", "#", "mailto:")


def markdown_files() -> list[Path]:
    return sorted(
        path for path in REPO.rglob("*.md")
        if not any(part in (".git", ".venv", "node_modules") for part in path.parts)
    )


def test_every_internal_documentation_link_resolves():
    broken = []
    for path in markdown_files():
        for label, target in LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(SKIP_PREFIXES):
                continue
            relative_target = target.split("#", 1)[0]
            if not relative_target:
                continue
            if not (path.parent / relative_target).resolve().exists():
                broken.append(
                    f"{path.relative_to(REPO)}: [{label}]({target})")
    assert not broken, "documentation links point at nothing:\n  " + "\n  ".join(broken)
