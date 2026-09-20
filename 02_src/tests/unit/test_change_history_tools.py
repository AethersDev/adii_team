"""Transform change history preserves the historical observation without enrichment."""
from __future__ import annotations

import json

import pytest
from adii.contracts import ToolCall
from adii.tools import (
    ReadOnlyDatabase,
    build_sql_tools,
    load_change_histories,
)


def markdown(*rows: str, newline: str = "\n") -> bytes:
    lines = [
        "# Transform change history",
        "",
        "| date | file | ticket | change |",
        "| --- | --- | --- | --- |",
        *rows,
        "",
    ]
    return newline.join(lines).encode("utf-8")


def write_bundle(folder, source: bytes, *, history_id: str = "transform-changes",
                 filename: str = "CHANGE_HISTORY.md", extras: dict[str, bytes] | None = None):
    (folder / "change_history_map.json").write_text(
        json.dumps({history_id: filename}), encoding="utf-8")
    sources = folder / "change_history_sources"
    sources.mkdir()
    (sources / filename).write_bytes(source)
    for name, content in (extras or {}).items():
        (sources / name).write_bytes(content)


def executor(histories):
    database = ReadOnlyDatabase.in_memory("CREATE TABLE orders (id INTEGER);")
    return build_sql_tools(database, change_histories=histories)


def call(history_id: str = "transform-changes") -> ToolCall:
    return ToolCall("history-1", "get_change_history", {"history_id": history_id})


def test_historical_fields_values_and_newest_first_order_are_preserved(tmp_path):
    write_bundle(tmp_path, markdown(
        "| 2026-07-08 | `staging/stg_orders.sql` | DATA-412 | Restrict revenue. |",
        "| 2026-07-06 | `staging/stg_orders.sql` | DATA-400 | Add a comment. |",
    ))

    result = executor(load_change_histories(tmp_path)).execute(call())

    assert result.status == "OK"
    assert result.content == {
        "history_id": "transform-changes",
        "ordering": "NEWEST_FIRST",
        "changes": [
            {"date": "2026-07-08", "file": "`staging/stg_orders.sql`",
             "ticket": "DATA-412", "change": "Restrict revenue."},
            {"date": "2026-07-06", "file": "`staging/stg_orders.sql`",
             "ticket": "DATA-400", "change": "Add a comment."},
        ],
        "count": 2,
        "truncated": False,
        "evidence_id": result.content["evidence_id"],
    }
    assert result.content["evidence_id"].startswith("ev-")


def test_repeated_loading_and_observation_identity_are_deterministic(tmp_path):
    write_bundle(tmp_path, markdown(
        "| 2026-07-08 | `staging/stg_orders.sql` | DATA-412 | Restrict revenue. |"))

    first = executor(load_change_histories(tmp_path)).execute(call())
    second = executor(load_change_histories(tmp_path)).execute(call())

    assert first == second


def test_empty_configured_history_is_a_successful_complete_collection(tmp_path):
    write_bundle(tmp_path, markdown())

    result = executor(load_change_histories(tmp_path)).execute(call())

    assert result.status == "OK"
    assert result.content["changes"] == []
    assert result.content["count"] == 0
    assert result.content["truncated"] is False


def test_unknown_history_id_is_rejected_before_handler(tmp_path):
    write_bundle(tmp_path, markdown())

    result = executor(load_change_histories(tmp_path)).execute(call("other-history"))

    assert result.status == "REJECTED"
    assert "evidence_id" not in result.content


def test_history_not_configured_means_tool_is_absent(tmp_path):
    histories = load_change_histories(tmp_path)
    tools = build_sql_tools(
        ReadOnlyDatabase.in_memory("CREATE TABLE orders (id INTEGER);"),
        change_histories=histories or None,
    )

    assert histories == {}
    assert "get_change_history" not in tools.names


@pytest.mark.parametrize("row", [
    "not a table row",
    "| 2026-07-08 | file.sql | DATA-412 | |",
    "| 08/07/2026 | file.sql | DATA-412 | Changed. |",
])
def test_malformed_rows_fail_closed(tmp_path, row):
    write_bundle(tmp_path, markdown(row))

    with pytest.raises(ValueError, match="malformed|ISO"):
        load_change_histories(tmp_path)


def test_duplicate_ticket_ids_fail_closed(tmp_path):
    write_bundle(tmp_path, markdown(
        "| 2026-07-08 | a.sql | DATA-412 | First. |",
        "| 2026-07-07 | b.sql | DATA-412 | Second. |",
    ))

    with pytest.raises(ValueError, match="duplicate change history ticket"):
        load_change_histories(tmp_path)


def test_non_newest_first_rows_fail_closed(tmp_path):
    write_bundle(tmp_path, markdown(
        "| 2026-07-07 | a.sql | DATA-400 | Earlier. |",
        "| 2026-07-08 | b.sql | DATA-412 | Later. |",
    ))

    with pytest.raises(ValueError, match="newest-first"):
        load_change_histories(tmp_path)


def test_change_history_bundle_is_closed(tmp_path):
    write_bundle(tmp_path, markdown(), extras={"answer_key.json": b"hidden"})

    with pytest.raises(ValueError, match=r"unbound=\['answer_key.json'\]"):
        load_change_histories(tmp_path)


def test_change_history_bundle_refuses_symlinks(tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_bytes(markdown())
    (tmp_path / "change_history_map.json").write_text(
        json.dumps({"transform-changes": "CHANGE_HISTORY.md"}), encoding="utf-8")
    sources = tmp_path / "change_history_sources"
    sources.mkdir()
    (sources / "CHANGE_HISTORY.md").symlink_to(outside)

    with pytest.raises(ValueError, match="regular files only"):
        load_change_histories(tmp_path)


def test_source_bytes_preserve_crlf_and_lf_exactly(tmp_path):
    raw = markdown(
        "| 2026-07-08 | `staging/stg_orders.sql` | DATA-412 | Changed. |",
        newline="\r\n",
    )
    write_bundle(tmp_path, raw)

    assert load_change_histories(tmp_path)["transform-changes"].source.encode("utf-8") == raw


def test_complete_collection_bound_fails_before_registration(tmp_path):
    write_bundle(tmp_path, markdown(
        "| 2026-07-08 | a.sql | DATA-412 | First. |",
        "| 2026-07-07 | b.sql | DATA-411 | Second. |",
    ))

    with pytest.raises(ValueError, match="refusing a partial collection"):
        load_change_histories(tmp_path, max_records=1)


@pytest.mark.parametrize("filename", ["../history.md", "nested/history.md", "/tmp/x.md"])
def test_change_history_bundle_refuses_source_paths(tmp_path, filename):
    (tmp_path / "change_history_map.json").write_text(
        json.dumps({"transform-changes": filename}), encoding="utf-8")
    (tmp_path / "change_history_sources").mkdir()

    with pytest.raises(ValueError, match="package-local filename"):
        load_change_histories(tmp_path)


@pytest.mark.parametrize("raw_date", ["20260708", "2026-W27-3", "2026-07-08T00:00", "2026-7-8"])
def test_a_date_in_any_form_but_the_promised_one_is_refused(tmp_path, raw_date):
    """`date.fromisoformat` alone would take the first two and the model would see three
    spellings of one field; the history promises YYYY-MM-DD and nothing else."""
    write_bundle(tmp_path, markdown(f"| {raw_date} | a.sql | DATA-1 | Changed. |"))
    with pytest.raises(ValueError, match="ISO YYYY-MM-DD"):
        load_change_histories(tmp_path)


def test_a_well_formed_date_that_is_not_a_calendar_date_is_refused(tmp_path):
    write_bundle(tmp_path, markdown("| 2026-02-30 | a.sql | DATA-1 | Changed. |"))
    with pytest.raises(ValueError, match="not a calendar date"):
        load_change_histories(tmp_path)


def test_configured_history_ids_must_be_logical_not_paths():
    from adii.tools import ChangeHistory
    with pytest.raises(ValueError, match="logical identifier"):
        executor({"../answer_key": ChangeHistory("", ())})
