"""The submission ZIP is built from a tag, carries the evidence git ignores, lists every file
with its digest, and is the same bytes from the same inputs."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import tarfile
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "package_submission.py"
spec = importlib.util.spec_from_file_location("package_submission", SCRIPT)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def a_tar(files: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return out.getvalue()


def test_the_zip_is_the_tag_and_the_evidence_listed_by_digest_the_same_every_time(tmp_path):
    (tmp_path / "01_data" / "packs").mkdir(parents=True)
    (tmp_path / "01_data" / "packs" / "p.json").write_text("{}", encoding="utf-8")
    (tmp_path / "01_data" / "packs" / "p.report.md").write_text("# p", encoding="utf-8")
    (tmp_path / "01_data" / "runs" / "p-a-full-r1").mkdir(parents=True)
    (tmp_path / "01_data" / "runs" / "p-a-full-r1" / "record.json").write_text("{}", "utf-8")
    (tmp_path / "01_data" / "runs" / "other-run").mkdir()
    (tmp_path / "01_data" / "runs" / "other-run" / "record.json").write_text("{}", "utf-8")
    committed = {"02_src/adii/x.py": b"print(1)\n", "README.md": b"# ADII\n"}
    files = {**packager.tree(a_tar(committed)), **packager.evidence(tmp_path, ["p"])}
    first = packager.package(files, "freeze-x", ["p"])
    assert first == packager.package(files, "freeze-x", ["p"])          # the same bytes
    with zipfile.ZipFile(io.BytesIO(first)) as zipped:
        names = zipped.namelist()
        manifest = json.loads(zipped.read(packager.NAME))
        assert names[-1] == packager.NAME
        assert "01_data/runs/other-run/record.json" not in names         # only the named packs
        for name in names[:-1]:
            assert manifest["files"][name] == hashlib.sha256(zipped.read(name)).hexdigest()
    assert set(manifest["files"]) == {"02_src/adii/x.py", "README.md", "01_data/packs/p.json",
                                      "01_data/packs/p.report.md",
                                      "01_data/runs/p-a-full-r1/record.json"}
    assert (manifest["ref"], manifest["packs"]) == ("freeze-x", ["p"])
    with pytest.raises(ValueError, match="no pack 'q'"):
        packager.evidence(tmp_path, ["q"])


def test_a_zip_carrying_an_env_file_or_the_keys_prefix_is_refused(tmp_path, monkeypatch):
    key = "sk-proj-" + "a1b2c3d4e5f6g7h8i9j0k1l2"
    files = {"02_src/x.py": b"print(1)", "01_data/runs/r/record.json": key[:16].encode(),
             "sub/.env.local": b"X=1"}
    assert packager.leaks(files, key) == ["01_data/runs/r/record.json", "sub/.env.local"]
    assert packager.leaks({"02_src/x.py": b"print(1)"}, key) == []
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env.local").write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
    assert packager.configured_key(tmp_path) == key
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-the-environment-0000")
    assert packager.configured_key(tmp_path) == "sk-from-the-environment-0000"
