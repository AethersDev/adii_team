"""What the freeze digests, git must carry.

A freeze names every file of the evaluated system by digest (adii.evaluation.lock), and the
tag is what the ZIP, the clean machines and every clone are built from. A file under the
frozen trees that git ignores is digested from one machine's disk and shipped nowhere: on 24
Sep 2026 `*.log` in .gitignore kept all 48 `vendor_receipts.log` evidence files out of the
repository, and every incident package failed to load from the tag while passing here.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from adii.evaluation import lock

REPO = Path(__file__).resolve().parents[3]


def test_no_file_the_freeze_digests_is_ignored_by_git():
    if not (REPO / ".git").exists():
        pytest.skip("an export of the repository: git's rules do not apply to it")
    paths = "\n".join(lock.files(REPO)) + "\n"
    ignored = subprocess.run(["git", "check-ignore", "--no-index", "--stdin"], cwd=REPO,
                             input=paths, capture_output=True, text=True).stdout.split()
    assert not ignored, f"{len(ignored)} frozen file(s) git will never carry: {ignored[:5]}"
