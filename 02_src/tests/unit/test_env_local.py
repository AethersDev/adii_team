"""The operator's `.env.local`: one name read into the environment when the shell has none,
strictly, and never over a value the shell already set."""
from __future__ import annotations

import os

import pytest
from adii.runtime.__main__ import load_env_local

FAKE = "not-a-real-key-for-this-test"


@pytest.fixture
def no_key(monkeypatch):
    """The shell has no key; monkeypatch puts the environment back afterwards, whatever the
    loader set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


def written(tmp_path, text: str):
    (tmp_path / ".env.local").write_text(text, encoding="utf-8")
    return tmp_path


def test_the_one_name_is_read_when_the_environment_lacks_it(tmp_path, no_key):
    load_env_local(written(tmp_path, f"# the key\n\nOTHER=ignored\nOPENAI_API_KEY={FAKE}\n"))
    assert os.environ["OPENAI_API_KEY"] == FAKE and "OTHER" not in os.environ


def test_a_value_already_in_the_environment_is_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "from-the-shell")
    load_env_local(written(tmp_path, f"OPENAI_API_KEY={FAKE}\n"))
    assert os.environ["OPENAI_API_KEY"] == "from-the-shell"


def test_no_file_and_an_empty_value_both_leave_the_environment_alone(tmp_path, no_key):
    load_env_local(tmp_path)
    assert "OPENAI_API_KEY" not in os.environ
    load_env_local(written(tmp_path, "OPENAI_API_KEY=\n"))
    assert "OPENAI_API_KEY" not in os.environ


@pytest.mark.parametrize("line, problem", [
    ("export OPENAI_API_KEY=x", "expected NAME=value"),
    ("OPENAI_API_KEY", "expected NAME=value"),
    ('OPENAI_API_KEY="quoted-value"', "OPENAI_API_KEY must be the bare value, unquoted"),
    ("OPENAI_API_KEY='quoted-value'", "OPENAI_API_KEY must be the bare value, unquoted"),
])
def test_anything_but_bare_name_value_lines_is_refused_by_number_never_by_value(
        tmp_path, no_key, line, problem):
    with pytest.raises(ValueError) as refused:
        load_env_local(written(tmp_path, f"# first\n{line}\n"))
    assert str(refused.value) == f".env.local line 2: {problem}"
    assert "quoted-value" not in str(refused.value) and "OPENAI_API_KEY" not in os.environ
