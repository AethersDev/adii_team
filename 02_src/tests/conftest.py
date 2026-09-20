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
