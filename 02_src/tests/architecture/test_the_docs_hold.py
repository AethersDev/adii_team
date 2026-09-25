"""The team's own documents and lineage, held by tests — the repository's, never the ZIP's
(02_src/scripts/package_submission.py leaves this file out, with the documents it reads).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from .test_boundaries import imported_modules, relative, source_files

SRC = Path(__file__).resolve().parents[2] / "adii"

# Packages that live in private repositories nobody here can check out. There is no
# adapter, no shared package, and no path on disk: an import of one of these is not a
# boundary to review later, it is code that builds on exactly one machine.
PRIVATE_PACKAGES = {"adii_env", "adii_eval", "adii_investigator"}

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


