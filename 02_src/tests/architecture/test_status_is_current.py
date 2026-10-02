"""Current status is generated, so it cannot quietly become fiction.

A hand-maintained status page is wrong within a fortnight and then actively misleads the
next person to read it — worse than not having one. This regenerates it and fails if the
committed file has drifted, which makes staleness a red build rather than a discovery.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2]


def _sync_status():
    path = SRC / "scripts" / "sync_status.py"
    spec = importlib.util.spec_from_file_location("sync_status", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_status_matches_the_repository():
    sync_status = _sync_status()
    committed = (SRC / "docs" / "current_status.md").read_text(encoding="utf-8")
    assert committed == sync_status.render(), (
        "docs/current_status.md is stale. Run python 02_src/scripts/sync_status.py. "
        "Do not edit that file by hand — milestone marks live in build_plan.md and "
        "everything else is read off the code.")


def test_the_status_page_still_reports_the_things_that_matter():
    """If a section is dropped, the page stops answering the question it exists for:
    what works, what does not exist yet, and how to check both."""
    text = (SRC / "docs" / "current_status.md").read_text(encoding="utf-8")
    for section in ("## Milestones", "## What exists", "## Scaffold only",
                    "## Verification"):
        assert section in text, f"current_status.md no longer has {section}"


def test_the_reading_order_documents_exist():
    """README, system map, build plan and status are what a newcomer — or an AI asked to
    work here — is told to read. A dangling pointer in that list is worse than no list."""
    for name in ("system_map.md", "build_plan.md", "glossary.md",
                 "current_status.md", "architecture.md"):
        path = SRC / "docs" / name
        assert path.is_file(), f"02_src/docs/{name} is missing"
        assert len(path.read_text(encoding="utf-8").split()) > 100, (
            f"02_src/docs/{name} is too thin to orient anyone")
