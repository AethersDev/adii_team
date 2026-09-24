"""The admissibility square's generator (final plan 4.5): four scripted proposals on the demo
company's fix case, through the real runtime, authorizer and validator, archived as runs —
and only from the frozen commit."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from adii.evaluation import lock

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "admissibility_square.py"
spec = importlib.util.spec_from_file_location("admissibility_square", SCRIPT)
square = importlib.util.module_from_spec(spec)
spec.loader.exec_module(square)


def test_each_cell_is_the_authorities_answer_and_is_archived_like_any_run(tmp_path, monkeypatch):
    monkeypatch.setattr(lock, "newest", lambda: {"name": "freeze-2026-01-01"})
    monkeypatch.setattr(lock, "drift", lambda freeze: [])
    monkeypatch.setattr(square, "ARCHIVE", tmp_path)
    assert square.main([]) == 0
    runs = {p.name.removeprefix("square-freeze-2026-01-01-"): p for p in tmp_path.iterdir()}
    assert sorted(runs) == ["admissible", "cannot-apply", "hides-the-symptom", "not-allowed"]
    seen = {}
    for cell, folder in runs.items():
        assert {p.name for p in folder.iterdir()} == {"receipt.json", "trace.jsonl",
                                                      "record.json"}
        record = json.loads((folder / "record.json").read_text(encoding="utf-8"))
        receipt = json.loads((folder / "receipt.json").read_text(encoding="utf-8"))
        assert "a scripted proposal judged by the real authorizer and validator" in \
            receipt["reason"]
        assert record["decision"]["disposition"] == "REPAIR" and record["decision"]["evidence_refs"]
        seen[cell] = (record["authorization"]["authorized"], record["validation"]["accepted"],
                      record["authorization"]["denied_paths"], record["validation"]["checks_run"])
    assert seen["admissible"][:2] == (True, True)
    assert seen["hides-the-symptom"][:2] == (True, False) and len(seen["hides-the-symptom"][3]) > 1
    assert seen["not-allowed"][:3] == (False, True, [square.MART])   # works, but not allowed
    assert seen["cannot-apply"][:2] == (True, False) and seen["cannot-apply"][3] == ["rebuild"]
    assert square.main([]) == 1                        # one square per freeze: labels are forever


def test_the_square_is_generated_only_from_the_frozen_commit(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(square, "ARCHIVE", tmp_path)
    monkeypatch.setattr(lock, "newest", lambda: None)
    assert square.main([]) == 2 and "no freeze has been taken" in capsys.readouterr().out
    monkeypatch.setattr(lock, "newest", lambda: {"name": "freeze-2026-01-01"})
    monkeypatch.setattr(lock, "drift", lambda freeze: ["02_src/adii/runtime/run.py"])
    assert square.main([]) == 2 and "no longer matches" in capsys.readouterr().out
    assert not list(tmp_path.iterdir())
