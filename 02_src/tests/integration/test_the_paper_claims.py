"""The paper held to its evidence (02_src/scripts/paper_claims.py), and each check shown to fail.

The published archives match the run manifest and the committed pack files; a second
implementation of the verdicts agrees with the scorer on every run; and every reported result
the paper prints is what the evidence renders. Each of the three is also fed a changed input
here, because a check is demonstrated when breaking what it reads makes it disagree.
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "paper_claims.py"
spec = importlib.util.spec_from_file_location("paper_claims", SCRIPT)
claims = importlib.util.module_from_spec(spec)
sys.modules["paper_claims"] = claims        # a dataclass resolves its module by name
spec.loader.exec_module(claims)

MANIFEST = json.loads(claims.MANIFEST.read_text(encoding="utf-8"))
PAPER = claims.PAPER.read_text(encoding="utf-8")
FIGURE = claims.FIGURE_2.read_text(encoding="utf-8")


def test_the_published_archives_match_the_manifest_and_the_committed_packs():
    assert claims.archive_findings(claims.published(), MANIFEST) == []


def test_a_changed_byte_in_an_archive_is_a_finding():
    archives = claims.published()
    files = archives["ADII_local_qwen_pack.zip"]
    path = next(p for p in files if p.endswith("/record.json"))
    files[path] += b" "
    assert claims.archive_findings(archives, MANIFEST) == [
        f"ADII_local_qwen_pack.zip: {path} does not match the manifest"]


def test_two_entries_on_one_path_are_refused():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("run\\record.json", "{}")
        archive.writestr("run/record.json", "{}")
    with pytest.raises(ValueError, match="two entries are run/record.json"):
        claims.entries(buffer.getvalue(), "two.zip")


def test_the_verdicts_here_agree_with_the_scorer_on_every_run():
    assert claims.agreement(claims.runs()) == []


def test_a_scorer_that_called_a_right_run_wrong_would_disagree():
    runs = claims.runs()
    run = next(r for r in runs if r.decision and claims.right(r))
    changed = tuple(replace(r, scored={**r.scored, "category": "failure"}) if r is run else r
                    for r in runs)
    assert claims.agreement(changed) == [f"{run.label}: here right, the scorer failure"]


def test_every_reported_result_is_what_the_evidence_says():
    assert claims.failures(PAPER, FIGURE, claims.claims()) == []


@pytest.mark.parametrize(("printed", "changed"), [
    ("| Qwen3-4B, REPAIR | 0/27 | 0 |", "| Qwen3-4B, REPAIR | 1/27 | 0 |"),
    ("772 of 1,504 delivered orders staged", "771 of 1,504 delivered orders staged"),
    ("| gpt-6-sol | full | 12/12 |", "| gpt-6-sol | full | 11/12 |"),
])
def test_a_changed_result_in_the_paper_is_a_failure(printed, changed):
    assert printed in PAPER
    failed = claims.failures(PAPER.replace(printed, changed), FIGURE, claims.claims())
    assert len(failed) == 1 and printed in failed[0]
