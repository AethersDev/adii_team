"""The investigator can read a frozen transform, but cannot choose what backing data opens."""
from __future__ import annotations

import json

import pytest
from adii.contracts import ToolCall
from adii.tools import ReadOnlyDatabase, build_sql_tools, load_transform_sources


def executor(sources: dict[str, str], *, max_chars: int = 100_000):
    database = ReadOnlyDatabase.in_memory("CREATE TABLE orders (id INTEGER);")
    return build_sql_tools(
        database, transform_sources=sources, max_transform_chars=max_chars)


def call(transform_id: str) -> ToolCall:
    return ToolCall(
        call_id="transform-1",
        name="get_transform",
        arguments={"transform_id": transform_id},
    )


def test_declared_logical_id_returns_complete_frozen_source_with_evidence():
    source = "select id from {{ ref('orders') }}\n"
    result = executor({"stg_orders": source}).execute(call("stg_orders"))

    assert result.status == "OK"
    assert result.content == {
        "transform_id": "stg_orders",
        "source": source,
        "characters": len(source),
        "max_chars": 100_000,
        "truncated": False,
        "evidence_id": result.content["evidence_id"],
    }
    assert result.content["evidence_id"].startswith("ev-")


def test_schema_is_the_discovery_surface_and_is_deterministically_sorted():
    tools = executor({"z_summary": "select 1", "a_orders": "select 2"})
    schema = next(item for item in tools.advertised() if item["name"] == "get_transform")

    assert schema["parameters"]["properties"]["transform_id"]["enum"] == [
        "a_orders", "z_summary"]


@pytest.mark.parametrize("transform_id", ["../answer_key", "transforms/orders.sql", "a\\b"])
def test_b3_configured_transform_ids_must_be_logical_not_paths(transform_id):
    with pytest.raises(ValueError, match="logical identifier"):
        executor({transform_id: "select 1"})


def test_unregistered_or_traversal_identifier_is_rejected_before_handler():
    result = executor({"stg_orders": "select 1"}).execute(call("../answer_key"))

    assert result.status == "REJECTED"
    assert "must be one of ['stg_orders']" in result.content["error"]
    assert "evidence_id" not in result.content


def test_source_mapping_is_snapshotted_when_the_surface_is_built():
    sources = {"stg_orders": "select 1"}
    tools = executor(sources)
    sources["stg_orders"] = "select secret from answer_key"

    result = tools.execute(call("stg_orders"))
    assert result.content["source"] == "select 1"


def test_oversized_source_fails_closed_instead_of_returning_a_partial_transform():
    with pytest.raises(ValueError, match="refusing a partial transform"):
        executor({"stg_orders": "12345"}, max_chars=4)


def test_identical_sources_produce_identical_observation_ids():
    first = executor({"stg_orders": "select 1"}).execute(call("stg_orders"))
    second = executor({"stg_orders": "select 1"}).execute(call("stg_orders"))

    assert first.content["evidence_id"] == second.content["evidence_id"]


def test_existing_sql_only_surface_is_unchanged_without_transform_sources():
    database = ReadOnlyDatabase.in_memory("CREATE TABLE orders (id INTEGER);")
    assert build_sql_tools(database).names == ("get_schema", "run_sql")


def write_bundle(folder, mapping: dict[str, str], sources: dict[str, str]):
    (folder / "transform_map.json").write_text(json.dumps(mapping), encoding="utf-8")
    source_dir = folder / "transform_sources"
    source_dir.mkdir()
    for filename, source in sources.items():
        # bytes, not write_text: on Windows write_text turns "\n" into "\r\n", and the
        # loader returns exactly what is on disk — which is the point of the test
        (source_dir / filename).write_bytes(source.encode("utf-8"))


def test_incident_bundle_loads_exact_source_under_logical_identity(tmp_path):
    write_bundle(tmp_path, {"stg_orders": "orders.sql"}, {"orders.sql": "select 1\n"})

    assert load_transform_sources(tmp_path) == {"stg_orders": "select 1\n"}


def test_incident_bundle_preserves_source_line_endings_exactly(tmp_path):
    write_bundle(tmp_path, {"stg_orders": "orders.sql"}, {})
    raw = b"select id\r\nfrom orders\r\n"
    (tmp_path / "transform_sources" / "orders.sql").write_bytes(raw)

    assert load_transform_sources(tmp_path)["stg_orders"].encode("utf-8") == raw


@pytest.mark.parametrize("filename", ["../answer.sql", "nested/orders.sql", "/tmp/x.sql"])
def test_incident_bundle_refuses_source_paths(tmp_path, filename):
    write_bundle(tmp_path, {"stg_orders": filename}, {})

    with pytest.raises(ValueError, match="package-local filename"):
        load_transform_sources(tmp_path)


def test_incident_bundle_refuses_unbound_content(tmp_path):
    write_bundle(
        tmp_path,
        {"stg_orders": "orders.sql"},
        {"orders.sql": "select 1", "answer_key.json": "hidden"},
    )

    with pytest.raises(ValueError, match=r"unbound=\['answer_key.json'\]"):
        load_transform_sources(tmp_path)


def test_incident_bundle_refuses_a_symlinked_source(tmp_path):
    outside = tmp_path / "outside.sql"
    outside.write_text("secret", encoding="utf-8")
    write_bundle(tmp_path, {"stg_orders": "orders.sql"}, {})
    (tmp_path / "transform_sources" / "orders.sql").symlink_to(outside)

    with pytest.raises(ValueError, match="regular files only"):
        load_transform_sources(tmp_path)


def test_incident_bundle_refuses_a_map_that_binds_one_id_twice(tmp_path):
    """Plain JSON would keep the last binding and the archived map would say two things."""
    write_bundle(tmp_path, {}, {"x.sql": "x", "y.sql": "y"})
    (tmp_path / "transform_map.json").write_text(
        '{"a": "x.sql", "a": "y.sql", "b": "x.sql"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key 'a'"):
        load_transform_sources(tmp_path)
