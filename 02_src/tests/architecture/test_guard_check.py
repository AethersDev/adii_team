"""The guard-removal pass itself: its registry names real snippets, its neutralise-run-
restore leaves every file byte for byte as it was, and its verdicts mean what they say.
The suite is injected here, so these run in milliseconds; the real pass is
`python 02_src/scripts/guard_check.py`, in CI before freeze."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "guard_check.py"
spec = importlib.util.spec_from_file_location("guard_check", SCRIPT)
guard_check = importlib.util.module_from_spec(spec)
sys.modules["guard_check"] = guard_check      # dataclasses resolve annotations through here
spec.loader.exec_module(guard_check)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_every_registered_snippet_is_found_exactly_once():
    """A guard that moved is a guard that may be gone: the registry has to be found or fail."""
    for guard in guard_check.GUARDS:
        text = (guard_check.SRC / guard.file).read_text(encoding="utf-8")
        assert text.count(guard.snippet) == 1, guard.name


def test_every_track_that_has_code_has_guards_registered():
    tracks = {g.track for g in guard_check.GUARDS}
    assert {"A", "B", "D", "contracts"} <= tracks


def test_neutralise_run_restore_leaves_the_file_as_it_was():
    guard = guard_check.GUARDS[0]
    path = guard_check.SRC / guard.file
    before = digest(path)
    seen = {}

    def suite() -> bool:
        seen["neutralised"] = guard.neutralised in path.read_text(encoding="utf-8")
        return True

    assert guard_check.check(guard, suite) == "SURVIVED"
    assert seen["neutralised"] and digest(path) == before


def test_a_failing_suite_means_killed_and_a_missing_snippet_is_a_failure():
    guard = guard_check.GUARDS[0]
    assert guard_check.check(guard, lambda: False) == "KILLED"
    gone = replace(guard, snippet="this text is in no file\n")
    assert guard_check.check(gone, lambda: True) == "NOT FOUND"


def test_the_pass_fails_on_a_survivor_a_control_or_a_missing_snippet(capsys, monkeypatch):
    killed = guard_check.GUARDS[0]
    control = next(g for g in guard_check.GUARDS if g.control)
    survivor = replace(guard_check.GUARDS[1], name="X.survives")
    monkeypatch.setattr(guard_check, "GUARDS", (killed, control, survivor))
    verdict = {killed.name: False, control.name: True, survivor.name: True}
    current = {"name": None}

    def suite() -> bool:
        return verdict[current["name"]]

    def check(guard, suite_fn):                       # route each guard to its scripted verdict
        current["name"] = guard.name
        return "SURVIVED" if suite_fn() else "KILLED"

    monkeypatch.setattr(guard_check, "check", check)
    assert guard_check.main([], suite=suite) == 1
    out = capsys.readouterr().out
    assert f"KILLED     {killed.name}" in out
    assert f"SURVIVED   {control.name}  ← CONTROL SURVIVED" in out
    assert "SURVIVED   X.survives  ← no test depends on this guard" in out
    assert "1 of 3 guards demonstrated." in out and "Not demonstrated: " in out
    assert "%" not in out                             # survivors by name, never a percentage


def test_list_and_only(capsys):
    assert guard_check.main(["--list", "--only", "D"]) == 0
    out = capsys.readouterr().out
    assert "D.strict_json_on_write" in out and "(control)" in out and "A.evidence_gate" not in out


@pytest.mark.parametrize("guard", guard_check.GUARDS, ids=lambda g: g.name)
def test_each_neutralisation_changes_the_file(guard):
    assert guard.snippet != guard.neutralised
