"""Operational notices are frozen observations, addressed only by logical identity."""
from __future__ import annotations

import json

import pytest
from adii.contracts import ToolCall
from adii.tools import ReadOnlyDatabase, build_sql_tools, load_notice_sources


def executor(sources: dict[str, str], *, max_chars: int = 50_000):
    database = ReadOnlyDatabase.in_memory("CREATE TABLE orders (id INTEGER);")
    return build_sql_tools(database, notice_sources=sources, max_notice_chars=max_chars)


def call(notice_id: str) -> ToolCall:
    return ToolCall("notice-1", "get_notice", {"notice_id": notice_id})


def write_bundle(folder, mapping: dict[str, str], sources: dict[str, bytes]):
    (folder / "notice_map.json").write_text(json.dumps(mapping), encoding="utf-8")
    source_dir = folder / "notice_sources"
    source_dir.mkdir()
    for filename, content in sources.items():
        (source_dir / filename).write_bytes(content)


def test_declared_notice_returns_complete_frozen_content_with_evidence():
    content = "Vendor: amounts change from cents to dollars on 2026-03-08.\n"
    result = executor({"vendor-unit-change": content}).execute(call("vendor-unit-change"))

    assert result.status == "OK"
    assert result.content["notice_id"] == "vendor-unit-change"
    assert result.content["content"] == content
    assert result.content["characters"] == len(content)
    assert result.content["truncated"] is False
    assert result.content["evidence_id"].startswith("ev-")


def test_notice_schema_is_deterministic_discovery_surface():
    tools = executor({"z-commercial": "z", "a-vendor": "a"})
    schema = next(item for item in tools.advertised() if item["name"] == "get_notice")

    assert schema["parameters"]["properties"]["notice_id"]["enum"] == [
        "a-vendor", "z-commercial"]


@pytest.mark.parametrize("notice_id", ["../answer_key", "notices/vendor.txt", "a\\b"])
def test_configured_notice_ids_must_be_logical_not_paths(notice_id):
    with pytest.raises(ValueError, match="logical identifier"):
        executor({notice_id: "text"})


def test_undeclared_notice_is_rejected_before_handler():
    result = executor({"vendor-unit-change": "text"}).execute(call("../answer_key"))

    assert result.status == "REJECTED"
    assert "evidence_id" not in result.content


def test_notice_mapping_is_snapshotted():
    sources = {"vendor-unit-change": "original"}
    tools = executor(sources)
    sources["vendor-unit-change"] = "changed"

    assert tools.execute(call("vendor-unit-change")).content["content"] == "original"


def test_oversized_notice_fails_closed_instead_of_truncating():
    with pytest.raises(ValueError, match="refusing a partial notice"):
        executor({"vendor-unit-change": "12345"}, max_chars=4)


def test_notice_bundle_preserves_exact_utf8_bytes(tmp_path):
    raw = b"Vendor notice\r\nEffective tomorrow.\r\n"
    write_bundle(
        tmp_path, {"vendor-unit-change": "vendor.txt"}, {"vendor.txt": raw})

    assert load_notice_sources(tmp_path)["vendor-unit-change"].encode("utf-8") == raw


@pytest.mark.parametrize("filename", ["../answer.txt", "nested/notice.txt", "/tmp/x.txt"])
def test_notice_bundle_refuses_source_paths(tmp_path, filename):
    write_bundle(tmp_path, {"vendor-unit-change": filename}, {})

    with pytest.raises(ValueError, match="package-local filename"):
        load_notice_sources(tmp_path)


def test_notice_bundle_refuses_unbound_content(tmp_path):
    write_bundle(
        tmp_path,
        {"vendor-unit-change": "vendor.txt"},
        {"vendor.txt": b"notice", "answer_key.json": b"hidden"},
    )

    with pytest.raises(ValueError, match=r"unbound=\['answer_key.json'\]"):
        load_notice_sources(tmp_path)


def test_notice_bundle_refuses_symlinked_content(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    write_bundle(tmp_path, {"vendor-unit-change": "vendor.txt"}, {})
    (tmp_path / "notice_sources" / "vendor.txt").symlink_to(outside)

    with pytest.raises(ValueError, match="regular files only"):
        load_notice_sources(tmp_path)
