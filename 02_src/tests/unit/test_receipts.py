"""Inherited D8 as tests: the receipt is on disk, complete, before the irreversible call —
proven by killing the process the instant after it is written — and every archived run
carries one from before it ran."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from adii.reporting.receipts import NAME, SCHEMA, read_receipt, write_receipt
from adii.runtime.__main__ import main

SRC = Path(__file__).resolve().parents[2]


def test_the_receipt_survives_a_process_killed_right_after_the_write(tmp_path):
    """os._exit skips every Python-level flush and handler, which is as close to a kill as a
    test can get on every platform the team uses. What is on disk afterwards is only what
    write_receipt itself flushed."""
    script = f"""
import os, sys
sys.path.insert(0, {str(SRC)!r})
from pathlib import Path
from adii.reporting.receipts import write_receipt
write_receipt(Path({str(tmp_path)!r}), label="about-to-spend",
              artefacts={{"incident": "sha256:abc", "world": "sha256:def"}},
              configuration={{"provider": "paid", "model": "m-1"}},
              reason="the first exposure of this incident to m-1, approved on 2026-09-16")
os._exit(137)
"""
    proc = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert proc.returncode == 137
    receipt = read_receipt(tmp_path / NAME)
    assert receipt["schema"] == SCHEMA and receipt["label"] == "about-to-spend"
    assert receipt["artefacts"] == {"incident": "sha256:abc", "world": "sha256:def"}
    assert receipt["configuration"]["model"] == "m-1" and "approved" in receipt["reason"]
    assert receipt["written_at"] and "source_revision" in receipt


def test_a_receipt_names_its_reason_or_is_refused(tmp_path):
    with pytest.raises(ValueError, match="reason"):
        write_receipt(tmp_path, label="x", artefacts={}, configuration={}, reason="  ")


def test_every_archived_run_carries_a_receipt_written_before_it_ran(tmp_path):
    assert main(["--incident", "demo-learning-001", "--provider", "scripted",
                 "--archive", str(tmp_path), "--label", "one", "--no-report"]) == 0
    folder = tmp_path / "one"
    receipt, record = read_receipt(folder / NAME), json.loads((folder / "record.json").read_text())
    assert receipt["label"] == "one" and receipt["configuration"] == record["configuration"]
    assert set(receipt["artefacts"]) == {"incident", "world", "protocol"}
    assert all(v.startswith("sha256:") for v in receipt["artefacts"].values())
    assert "nothing is spent" in receipt["reason"]
    assert os.stat(folder / NAME).st_mtime <= os.stat(folder / "record.json").st_mtime


def test_an_unknown_receipt_schema_is_refused(tmp_path):
    (tmp_path / NAME).write_text('{"schema": "adii.receipt/v9"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown receipt schema"):
        read_receipt(tmp_path / NAME)
