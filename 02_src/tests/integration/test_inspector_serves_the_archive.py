"""The inspector is read-only over the archive, and an archive that hides a broken run is
worse than one that shows it."""
from __future__ import annotations

from adii.demo.server import index
from adii.examples.walkthrough import main as walkthrough


def test_an_empty_archive_lists_nothing(tmp_path):
    assert index(tmp_path) == []


def test_an_archived_run_is_listed_with_what_a_run_list_needs(tmp_path):
    assert walkthrough(["--archive", str(tmp_path)]) == 0
    [row] = index(tmp_path)
    assert row["label"] == "demo-learning-001"
    assert row["termination"] == "submitted"
    assert row["disposition"] == "REPAIR" and row["validation"] == "ACCEPT"
    assert row["model"] is None and row["api_cost_usd"] == 0.0142


def test_an_unreadable_record_is_listed_not_hidden(tmp_path):
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "record.json").write_text(
        '{"schema": "adii.run_record/v9"}', encoding="utf-8")
    [row] = index(tmp_path)
    assert row["label"] == "broken" and "unknown record schema" in row["error"]
