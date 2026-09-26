"""Shared fixtures for the whole suite."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def no_operators_env_local(monkeypatch, tmp_path):
    """The credential loader looks for `.env.local` at the repository root — the operator's
    real file, on the operator's machine. No test may read it: every test sees the loader's
    root as its own empty temp folder, so a test that deletes OPENAI_API_KEY from the
    environment is testing the absence it thinks it is, and a real key never enters a test."""
    monkeypatch.setattr("adii.provider.credential.REPO", tmp_path)


@pytest.fixture
def symlink():
    """Make `link` point at `target`, or skip. Windows lets only administrators, or accounts in
    Developer Mode, create symlinks; on such a machine the attack a symlink test guards against
    cannot even be built, so the test has nothing to prove there and says why."""
    def make(link, target):
        try:
            link.symlink_to(target)
        except OSError as refused:          # WinError 1314: the privilege is not held
            pytest.skip(f"this machine cannot create a symlink ({refused.strerror}); "
                        "the refusal this test proves needs one")
    return make
