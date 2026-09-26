"""One closed bundle: the rules every evidence kind shares, held once."""
from __future__ import annotations

import json

import pytest
from adii.tools.packages import load_bundle, strict_json


def bundle(folder, mapping: str, files: dict[str, bytes]):
    (folder / "map.json").write_text(mapping, encoding="utf-8")
    (folder / "sources").mkdir()
    for name, content in files.items():
        (folder / "sources" / name).write_bytes(content)


def test_an_absent_bundle_is_none_and_a_present_one_is_its_map_and_its_files(tmp_path):
    assert load_bundle(tmp_path, "map.json", "sources") is None
    bundle(tmp_path, json.dumps({"b": "two.txt", "a": "one.txt"}),
           {"one.txt": b"1\r\n", "two.txt": b"2"})
    assert load_bundle(tmp_path, "map.json", "sources") == (
        {"b": "two.txt", "a": "one.txt"}, {"two.txt": "2", "one.txt": "1\r\n"})


def test_strict_json_takes_one_value_per_key_and_no_non_finite_number():
    assert strict_json('{"a": 1, "b": [1.5, "x"]}', artefact="m") == {"a": 1, "b": [1.5, "x"]}
    with pytest.raises(ValueError, match="duplicate JSON key 'a'"):
        strict_json('{"a": 1, "a": 2}', artefact="m")
    with pytest.raises(ValueError, match="non-finite JSON value 'NaN'"):
        strict_json('{"a": NaN}', artefact="m")
    with pytest.raises(ValueError, match="m is not valid JSON"):
        strict_json("{", artefact="m")


@pytest.mark.parametrize(("mapping", "said"), [
    ('{"a": "x.txt", "a": "y.txt", "b": "x.txt"}', "duplicate JSON key 'a'"),
    ('{"../key": "x.txt"}', "logical identifier"),
    ('{"": "x.txt"}', "logical identifier"),
    ('{"a": "../x.txt"}', "package-local filename"),
    ('{"a": 1}', "package-local filename"),
    ('{"a": "x.txt", "b": "x.txt"}', "exactly once"),
    ("[]", "non-empty object"),
    ("{}", "non-empty object"),
])
def test_a_map_that_does_not_bind_logical_ids_to_local_files_once_is_refused(tmp_path, mapping,
                                                                             said):
    bundle(tmp_path, mapping, {"x.txt": b"x", "y.txt": b"y"})
    with pytest.raises(ValueError, match=said):
        load_bundle(tmp_path, "map.json", "sources")


def test_a_table_keyed_bundle_accepts_any_non_empty_key(tmp_path):
    bundle(tmp_path, '{"raw orders/2026": "x.txt"}', {"x.txt": b"x"})
    mapping, _ = load_bundle(tmp_path, "map.json", "sources", keys=None)
    assert mapping == {"raw orders/2026": "x.txt"}
    with pytest.raises(ValueError, match="logical identifier"):
        load_bundle(tmp_path, "map.json", "sources")


def test_a_dangling_or_linked_map_is_refused_not_treated_as_absent(tmp_path, symlink):
    symlink((tmp_path / "map.json"), tmp_path / "nowhere")
    with pytest.raises(ValueError, match="regular file beside"):
        load_bundle(tmp_path, "map.json", "sources")
    (tmp_path / "map.json").unlink()
    real = tmp_path / "real"
    real.mkdir()
    (real / "x.txt").write_bytes(b"x")
    (tmp_path / "map.json").write_text('{"a": "x.txt"}', encoding="utf-8")
    symlink((tmp_path / "sources"), real)
    with pytest.raises(ValueError, match="regular file beside"):
        load_bundle(tmp_path, "map.json", "sources")
