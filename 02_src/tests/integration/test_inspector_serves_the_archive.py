"""The inspector is read-only over the archive, and an archive that hides a broken run is
worse than one that shows it."""
from __future__ import annotations

import socket

from adii.demo.server import index, main
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


def test_a_taken_port_is_a_message_not_a_traceback(capsys):
    """The most common way to start the inspector twice. It has to say which port and what
    to type, not dump socketserver's stack."""
    with socket.socket() as held:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):   # on Windows a second bind can steal a port
            held.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        held.bind(("127.0.0.1", 0))
        held.listen()
        port = held.getsockname()[1]
        assert main(port) == 1
    out = capsys.readouterr().out
    assert f"could not listen on 127.0.0.1:{port}" in out
    assert f"python -m adii.demo {port + 1}" in out
