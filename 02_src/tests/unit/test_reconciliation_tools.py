"""Reconciliation evidence is raw, ordered, bounded, and addressed only by logical ID."""
from __future__ import annotations

import json

import pytest
from adii.contracts import ToolCall
from adii.tools import (
    ReadOnlyDatabase,
    build_sql_tools,
    load_reconciliation_sources,
)


def write_bundle(folder, mapping: dict[str, str], sources: dict[str, bytes]):
    (folder / "reconciliation_map.json").write_text(json.dumps(mapping), encoding="utf-8")
    source_dir = folder / "reconciliation_sources"
    source_dir.mkdir()
    for filename, content in sources.items():
        (source_dir / filename).write_bytes(content)


def executor(sources: dict[str, str], **bounds):
    database = ReadOnlyDatabase.in_memory("CREATE TABLE orders (id INTEGER);")
    return build_sql_tools(database, reconciliation_sources=sources, **bounds)


def call(*, reconciliation_id: str = "upstream-feed", offset=None, limit=None) -> ToolCall:
    arguments = {"reconciliation_id": reconciliation_id}
    if offset is not None:
        arguments["offset"] = offset
    if limit is not None:
        arguments["limit"] = limit
    return ToolCall("reconciliation-1", "read_reconciliation", arguments)


def test_exact_ordered_lines_and_historical_default_window_are_preserved():
    lines = [f"event-{number:02d}" for number in range(49)]

    result = executor({"upstream-feed": "\n".join(lines) + "\n"}).execute(call())

    assert result.status == "OK"
    assert result.content == {
        "reconciliation_id": "upstream-feed",
        "offset": 0,
        "total_lines": 49,
        "returned": 49,
        "lines": lines,
        "truncated": False,
        "next_offset": None,
        "evidence_id": result.content["evidence_id"],
    }


def test_partial_window_reports_continuation_and_exact_total():
    result = executor({"upstream-feed": "first\nsecond\nthird\nfourth\n"}).execute(
        call(offset=1, limit=2))

    assert result.status == "OK"
    assert result.content["offset"] == 1
    assert result.content["total_lines"] == 4
    assert result.content["returned"] == 2
    assert result.content["lines"] == ["second", "third"]
    assert result.content["truncated"] is True
    assert result.content["next_offset"] == 3


def test_valid_window_beyond_end_is_successful_empty_evidence():
    result = executor({"upstream-feed": "first\nsecond\n"}).execute(
        call(offset=8, limit=20))

    assert result.status == "OK"
    assert result.content["offset"] == 8
    assert result.content["total_lines"] == 2
    assert result.content["returned"] == 0
    assert result.content["lines"] == []
    assert result.content["truncated"] is False
    assert result.content["next_offset"] is None


@pytest.mark.parametrize(("offset", "limit", "message"), [
    (-1, 1, "offset must be non-negative"),
    (0, 0, "limit must be between"),
    (0, -1, "limit must be between"),
    (0, 201, "limit must be between"),
])
def test_invalid_window_bounds_are_rejected(offset, limit, message):
    result = executor({"upstream-feed": "line\n"}).execute(
        call(offset=offset, limit=limit))

    assert result.status == "REJECTED"
    assert message in result.content["error"]
    assert "evidence_id" not in result.content


def test_undeclared_reconciliation_id_is_rejected_by_schema():
    result = executor({"upstream-feed": "line\n"}).execute(
        call(reconciliation_id="other-feed"))

    assert result.status == "REJECTED"
    assert "evidence_id" not in result.content


def test_reconciliation_tool_is_absent_when_not_configured(tmp_path):
    sources = load_reconciliation_sources(tmp_path)
    tools = build_sql_tools(
        ReadOnlyDatabase.in_memory("CREATE TABLE orders (id INTEGER);"),
        reconciliation_sources=sources or None,
    )

    assert sources == {}
    assert "read_reconciliation" not in tools.names


def test_known_unavailability_remains_ordinary_source_content():
    statement = "2026-07-08 ERROR entries for this interval were never written"

    result = executor({"upstream-feed": statement + "\n"}).execute(call())

    assert result.status == "OK"
    assert result.content["lines"] == [statement]


def test_bundle_is_closed(tmp_path):
    write_bundle(
        tmp_path,
        {"upstream-feed": "upstream.log"},
        {"upstream.log": b"line\n", "answer_key.json": b"hidden"},
    )

    with pytest.raises(ValueError, match=r"unbound=\['answer_key.json'\]"):
        load_reconciliation_sources(tmp_path)


def test_missing_declared_source_fails_loading(tmp_path):
    write_bundle(tmp_path, {"upstream-feed": "upstream.log"}, {})

    with pytest.raises(ValueError, match=r"missing=\['upstream.log'\]"):
        load_reconciliation_sources(tmp_path)


def test_symlinked_source_is_refused(tmp_path, symlink):
    outside = tmp_path / "outside.log"
    outside.write_text("secret\n", encoding="utf-8")
    write_bundle(tmp_path, {"upstream-feed": "upstream.log"}, {})
    symlink((tmp_path / "reconciliation_sources" / "upstream.log"), outside)

    with pytest.raises(ValueError, match="regular files only"):
        load_reconciliation_sources(tmp_path)


def test_invalid_utf8_fails_loading(tmp_path):
    write_bundle(
        tmp_path, {"upstream-feed": "upstream.log"}, {"upstream.log": b"\xff\xfe"})

    with pytest.raises(UnicodeDecodeError):
        load_reconciliation_sources(tmp_path)


def test_source_bytes_preserve_crlf_and_lf_exactly(tmp_path):
    raw = b"first\r\nsecond\nthird\r\n"
    write_bundle(
        tmp_path, {"upstream-feed": "upstream.log"}, {"upstream.log": raw})

    loaded = load_reconciliation_sources(tmp_path)

    assert loaded["upstream-feed"].encode("utf-8") == raw
    assert executor(loaded).execute(call()).content["lines"] == ["first", "second", "third"]


def test_source_size_bound_fails_before_model_execution(tmp_path):
    write_bundle(
        tmp_path, {"upstream-feed": "upstream.log"}, {"upstream.log": b"12345"})

    with pytest.raises(ValueError, match="max_source_bytes=4"):
        load_reconciliation_sources(tmp_path, max_source_bytes=4)


def test_individual_line_size_bound_fails_before_model_execution(tmp_path):
    write_bundle(
        tmp_path, {"upstream-feed": "upstream.log"}, {"upstream.log": b"12345\nx\n"})

    with pytest.raises(ValueError, match="max_line_bytes=4"):
        load_reconciliation_sources(tmp_path, max_line_bytes=4)


@pytest.mark.parametrize("filename", ["../feed.log", "nested/feed.log", "/tmp/feed.log"])
def test_bundle_refuses_source_paths(tmp_path, filename):
    write_bundle(tmp_path, {"upstream-feed": filename}, {})

    with pytest.raises(ValueError, match="package-local filename"):
        load_reconciliation_sources(tmp_path)


def test_repeated_loading_and_observation_identity_are_deterministic(tmp_path):
    write_bundle(
        tmp_path,
        {"upstream-feed": "upstream.log"},
        {"upstream.log": b"first\nsecond\n"},
    )

    first = executor(load_reconciliation_sources(tmp_path)).execute(call(limit=1))
    second = executor(load_reconciliation_sources(tmp_path)).execute(call(limit=1))

    assert first == second


def test_lines_are_physical_lines_and_nothing_else_splits_them():
    """A form feed, U+2028 or NEL inside a line stays inside it: the line count the model sees
    is the source's own, and the per-line bound cannot be slipped by a character that
    `str.splitlines` would treat as a line end."""
    content = executor({"upstream-feed": "a\x0cb c\x85d\ne\r\nf\rg"}).execute(call()).content
    assert content["lines"] == ["a\x0cb c\x85d", "e", "f", "g"]
    assert content["total_lines"] == 4
    with pytest.raises(ValueError, match="line 1 .* has 31 bytes, exceeding max_line_bytes=20"):
        executor({"upstream-feed": "x" * 15 + "\x0c" + "y" * 15 + "\n"},
                 max_reconciliation_line_bytes=20)


def test_configured_reconciliation_ids_must_be_logical_not_paths():
    with pytest.raises(ValueError, match="logical identifier"):
        executor({"../answer_key": "line\n"})


def test_a_map_with_a_duplicate_logical_id_is_refused(tmp_path):
    write_bundle(tmp_path, {}, {"x.log": b"x\n", "y.log": b"y\n"})
    (tmp_path / "reconciliation_map.json").write_text(
        '{"a": "x.log", "a": "y.log", "b": "x.log"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key 'a'"):
        load_reconciliation_sources(tmp_path)
