from __future__ import annotations

import json

import pytest
from adii.contracts import ToolCall
from adii.tools import ReadOnlyDatabase, build_sql_tools, load_declared_schemas

DECLARATION = {
    "source": "vendor.orders_feed",
    "schema_version": 3,
    "fields": {
        "amount": {
            "type": "number",
            "unit": "usd",
            "note": "Major units; v3 changed this from cents.",
        },
    },
}


def write_bundle(folder, mapping=None, sources=None):
    mapping = {"raw_orders": "raw_orders.json"} if mapping is None else mapping
    sources = {"raw_orders.json": json.dumps(DECLARATION)} if sources is None else sources
    (folder / "declared_schema_map.json").write_text(json.dumps(mapping), encoding="utf-8")
    source_dir = folder / "declared_schema_sources"
    source_dir.mkdir()
    for filename, content in sources.items():
        (source_dir / filename).write_bytes(content.encode("utf-8"))


def tools(declarations=None):
    database = ReadOnlyDatabase.in_memory(
        "CREATE TABLE raw_orders (id TEXT, amount INTEGER);"
        "CREATE TABLE other (id INTEGER);")
    return build_sql_tools(database, declared_schemas=declarations)


def schema(executor, table="raw_orders"):
    return executor.execute(ToolCall("schema", "get_schema", {"table": table}))


def test_physical_only_get_schema_is_exactly_unchanged():
    result = schema(tools())
    assert result.content == {
        "table": "raw_orders",
        "columns": ["id", "amount"],
        "ddl": "CREATE TABLE raw_orders (id TEXT, amount INTEGER)",
        "evidence_id": result.content["evidence_id"],
    }
    assert "declared_schema" not in result.content


def test_declared_values_are_exact_and_only_returned_for_the_bound_table(tmp_path):
    write_bundle(tmp_path)
    executor = tools(load_declared_schemas(tmp_path))

    result = schema(executor)
    assert result.content["columns"] == ["id", "amount"]
    assert result.content["ddl"] == "CREATE TABLE raw_orders (id TEXT, amount INTEGER)"
    assert result.content["declared_schema"] == DECLARATION
    assert "declared_schema" not in schema(executor, "other").content


def test_declared_mapping_is_snapshotted_and_not_inferred():
    assert "declared_schema" not in schema(tools()).content


def test_unknown_table_behavior_is_unchanged(tmp_path):
    write_bundle(tmp_path)
    result = schema(tools(load_declared_schemas(tmp_path)), "missing")
    assert result.status == "REJECTED" and "known tables" in result.content["error"]


def test_binding_to_a_table_absent_from_sqlite_fails_before_use(tmp_path):
    write_bundle(tmp_path, {"missing": "raw_orders.json"})
    with pytest.raises(ValueError, match="unknown tables: missing"):
        tools(load_declared_schemas(tmp_path))


def test_duplicate_table_binding_is_refused(tmp_path):
    write_bundle(tmp_path)
    (tmp_path / "declared_schema_map.json").write_text(
        '{"raw_orders":"one.json","raw_orders":"two.json"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key 'raw_orders'"):
        load_declared_schemas(tmp_path)


@pytest.mark.parametrize("source", ["{", "[]", '{"source":"x","schema_version":3}'])
def test_malformed_declaration_is_refused(tmp_path, source):
    write_bundle(tmp_path, sources={"raw_orders.json": source})
    with pytest.raises(ValueError, match="declared schema"):
        load_declared_schemas(tmp_path)


def test_missing_and_extra_artifacts_are_refused(tmp_path):
    write_bundle(tmp_path, sources={})
    with pytest.raises(ValueError, match="missing=.*raw_orders.json"):
        load_declared_schemas(tmp_path)

    extra = tmp_path / "extra"
    extra.mkdir()
    write_bundle(extra, sources={"raw_orders.json": json.dumps(DECLARATION), "hidden.json": "{}"})
    with pytest.raises(ValueError, match="unbound=.*hidden.json"):
        load_declared_schemas(extra)


def test_symlinked_artifact_is_refused(tmp_path, symlink):
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(DECLARATION), encoding="utf-8")
    write_bundle(tmp_path, sources={})
    symlink((tmp_path / "declared_schema_sources" / "raw_orders.json"), outside)
    with pytest.raises(ValueError, match="regular files only"):
        load_declared_schemas(tmp_path)


@pytest.mark.parametrize("filename", ["../schema.json", "nested/schema.json", "/tmp/x.json"])
def test_artifact_filename_must_be_one_package_local_name(tmp_path, filename):
    write_bundle(tmp_path, {"raw_orders": filename}, {})
    with pytest.raises(ValueError, match="one package-local filename"):
        load_declared_schemas(tmp_path)


def test_source_bytes_preserve_crlf_and_loading_is_deterministic(tmp_path):
    raw = (b'{\r\n  "source": "vendor.orders_feed",\r\n  "schema_version": 3,\r\n'
           b'  "fields": {"amount": {"type": "number", "unit": "usd"}}\r\n}\r\n')
    write_bundle(tmp_path, sources={})
    (tmp_path / "declared_schema_sources" / "raw_orders.json").write_bytes(raw)

    first = load_declared_schemas(tmp_path)
    second = load_declared_schemas(tmp_path)
    assert first == second
    assert first["raw_orders"].source.encode("utf-8") == raw
    assert schema(tools(first)).content["evidence_id"] == \
        schema(tools(second)).content["evidence_id"]
