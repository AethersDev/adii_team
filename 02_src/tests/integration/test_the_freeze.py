"""Phase 4, the freeze: what the final packs run on is named by digest before any of them
runs, a change after it is a new freeze version, and a registered pack runs only on it."""
from __future__ import annotations

import json

import pytest
from adii.evaluation import grid, lock


def test_the_newest_freeze_is_the_tree_the_gate_runs_on():
    """The rule of phase 4, executable: once a freeze is taken, any change to a frozen file
    fails here until a new freeze version is taken — never a silent engineering change."""
    freeze = lock.newest()
    if freeze is None:
        pytest.skip("no freeze has been taken yet")
    assert lock.drift(freeze) == [], f"changed since {freeze['name']}: take a new freeze version"
    assert freeze["digest"] == lock.digest(freeze["files"])
    assert freeze["packs"] == {p: lock.terms(p) for p in lock.PACKS}


def test_a_freeze_digests_the_system_and_notices_any_change(tmp_path):
    for path in ("02_src/adii/a.py", "02_src/adii/__pycache__/a.pyc", "01_data/incidents/x/w.sql",
                 "02_src/adii/evaluation/freezes/f.json", "requirements.txt", "pyproject.toml",
                 # cannot change the experiment, so never frozen: the page, and prose
                 "02_src/adii/demo/web/app.js", "02_src/adii/README.md",
                 "01_data/incidents/x/README.md",
                 "02_src/adii/evaluation/freezes/development/o.json"):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("x", encoding="utf-8")
    frozen = lock.files(tmp_path)
    assert sorted(frozen) == ["01_data/incidents/x/w.sql", "02_src/adii/a.py", "pyproject.toml",
                              "requirements.txt"]
    freeze = {"files": frozen}
    assert lock.drift(freeze, tmp_path) == []
    (tmp_path / "02_src/adii/a.py").write_text("y", encoding="utf-8")
    (tmp_path / "02_src/adii/b.py").write_text("new", encoding="utf-8")
    assert lock.drift(freeze, tmp_path) == ["02_src/adii/a.py", "02_src/adii/b.py"]


DECISION_E = {"final-sol": 12, "final-luna": 12, "final-gpt-4-1": 12, "final-held-out": 6}


def test_the_registered_packs_are_decision_e_and_one_extension_and_hold_no_burned_case():
    assert {p: len(lock.terms(p)["incidents"]) for p in lock.PACKS} == {
        **DECISION_E, "local-qwen3-4b": 12}
    assert not grid.BURNED & {i for p in lock.PACKS for i in lock.terms(p)["incidents"]}
    paid = {p: len(t["incidents"]) * sum(a != "always-escalate" for a in t["arms"])
            for p, t in ((p, lock.terms(p)) for p in DECISION_E)}
    assert sum(paid.values()) == 54
    assert all(abs(lock.terms(p)["pack_cap_usd"] - n * 0.51) < 1e-9 for p, n in paid.items())
    # the extension: the benchmark only, the held-out six untouched; decision E's bounds; local
    # and with no judge, so no other model takes part and nothing is paid for
    qwen = lock.terms("local-qwen3-4b")
    assert qwen["incidents"] == grid.PARTITION["benchmark"] and qwen["provider"] == "local"
    assert {k: qwen[k] for k in ("max_turns", "max_tokens")} == {
        k: lock.COMMON[k] for k in ("max_turns", "max_tokens")}
    assert qwen["judge_model"] is None and qwen["pack_cap_usd"] is None


HELD_OUT = ["--pack", "final-held-out", "--provider", "openai", "--model", "gpt-6-sol",
            "--reasoning-effort", "low", "--arms", "full", "--repeats", "1",
            "--partition", "held_out", "--max-turns", "20", "--max-cost-usd", "0.5",
            "--max-tokens", "4096", "--judge-model", "gpt-4.1-mini", "--pack-cap-usd", "3.06"]


def test_a_registered_pack_runs_only_on_the_freeze_with_its_frozen_terms(tmp_path, monkeypatch,
                                                                          capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-0123456789abcdefghijklmn")
    monkeypatch.setattr(grid, "run_cell", lambda *a: 0)
    where = ["--archive", str(tmp_path / "runs"), "--packs", str(tmp_path / "packs")]
    monkeypatch.setattr(lock, "newest", lambda: None)
    assert grid.main([*HELD_OUT, *where]) == 2
    assert "no freeze has been taken" in capsys.readouterr().out
    freeze = {"name": "freeze-test", "digest": "d", "files": {},
              "packs": {p: lock.terms(p) for p in lock.PACKS}}
    monkeypatch.setattr(lock, "newest", lambda: freeze)
    monkeypatch.setattr(lock, "drift", lambda f: ["02_src/adii/a.py"])
    assert grid.main([*HELD_OUT, *where]) == 2
    assert "1 frozen file(s) changed since freeze-test" in capsys.readouterr().out
    monkeypatch.setattr(lock, "drift", lambda f: [])
    assert grid.main([*HELD_OUT[:-1], "3.50", *where]) == 2
    assert "these terms differ from the frozen ones" in capsys.readouterr().out
    assert not (tmp_path / "packs").exists()
    assert grid.main([*HELD_OUT, *where]) == 0
    receipt = json.loads((tmp_path / "packs" / "final-held-out.json").read_text("utf-8"))
    assert receipt["freeze"] == {"name": "freeze-test", "digest": "d"}



QWEN = ["--pack", "local-qwen3-4b", "--provider", "local", "--model",
        "Qwen3-4B-Instruct-2507-4bit", "--endpoint", "http://127.0.0.1:8090/v1", "--served-as",
        "default_model", "--weights", "WEIGHTS", "--arms", "full", "--repeats", "3",
        "--max-tokens", "4096"]


def test_the_extensions_documented_command_is_its_registered_terms(tmp_path, monkeypatch,
                                                                     capsys):
    """docs/qwen_local_extension.md gives this command; on the frozen weights it is the pack's
    frozen terms, and on any other weights it is refused before anything runs. It needs no
    credential: nothing in it is paid for."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(grid, "run_cell", lambda *a: 0)
    freeze = {"name": "freeze-test", "digest": "d", "files": {},
              "packs": {p: lock.terms(p) for p in lock.PACKS}}
    monkeypatch.setattr(lock, "newest", lambda: freeze)
    monkeypatch.setattr(lock, "drift", lambda f: [])
    where = ["--archive", str(tmp_path / "runs"), "--packs", str(tmp_path / "packs")]
    monkeypatch.setattr(grid, "weights_digest", lambda d: "other weights")
    assert grid.main([*QWEN, *where]) == 2
    assert "these terms differ from the frozen ones" in capsys.readouterr().out
    frozen = lock.PACKS["local-qwen3-4b"]["weights_sha256"]
    monkeypatch.setattr(grid, "weights_digest", lambda d: frozen)
    assert grid.main([*QWEN, *where]) == 0
    receipt = json.loads((tmp_path / "packs" / "local-qwen3-4b.json").read_text("utf-8"))
    assert receipt["freeze"] == {"name": "freeze-test", "digest": "d"}


def test_the_newest_freeze_is_the_latest_date_never_the_last_name(tmp_path):
    for name in ("freeze-2026-09-24", "freeze-2026-09-24-2", "freeze-2026-09-30", "notes"):
        (tmp_path / f"{name}.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    assert lock.newest(tmp_path)["name"] == "freeze-2026-09-30"
    (tmp_path / "freeze-2026-09-30.json").unlink()
    assert lock.newest(tmp_path)["name"] == "freeze-2026-09-24-2"
    assert lock.main(["--name", "freeze-final"]) == 2          # never a name that sorts wrong
