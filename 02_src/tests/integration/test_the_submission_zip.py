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
    (tmp_path / "01_data" / "packs" / "p.json").write_text(json.dumps(
        {"pack": "p", "incidents": ["a"], "arms": ["full"], "repeats": 1}), encoding="utf-8")
    (tmp_path / "01_data" / "packs" / "p.report.md").write_text("# p", encoding="utf-8")
    for label in ("p-a-full-r1", "p-zzz-not-a-cell", "other-run", "square-x-not-allowed"):
        (tmp_path / "01_data" / "runs" / label).mkdir(parents=True)
        (tmp_path / "01_data" / "runs" / label / "record.json").write_text("{}", "utf-8")
    committed = {"02_src/adii/x.py": b"print(1)\n", "README.md": b"# ADII\n",
                 "02_src/docs/final_plan.md": b"# the team's\n"}
    files = {**packager.tree(a_tar(committed)),
             **packager.evidence(tmp_path, ["p"], ["square-x-not-allowed"])}
    first = packager.package(files)
    assert first == packager.package(files)                            # the same bytes
    with zipfile.ZipFile(io.BytesIO(first)) as zipped:
        assert all(n.startswith(packager.FOLDER + "/") for n in zipped.namelist())
        names = {n.removeprefix(packager.FOLDER + "/") for n in zipped.namelist()}
    assert names == {"02_src/adii/x.py", "README.md", "01_data/packs/p.json",
                     "01_data/packs/p.report.md", "01_data/runs/p-a-full-r1/record.json",
                     "01_data/runs/square-x-not-allowed/record.json"}   # only the named packs'
    lines = packager.checksums(files).splitlines()       # beside the ZIP, never in it
    assert [line.split("  ", 1)[1] for line in lines] == \
        [f"{packager.FOLDER}/{n}" for n in sorted(names)]
    assert f"{hashlib.sha256(b'# ADII' + bytes([10])).hexdigest()}  {packager.FOLDER}/README.md" \
        in lines
    with pytest.raises(ValueError, match="no run 'other'"):          # a named run, or nothing
        packager.evidence(tmp_path, [], ["other"])
    with pytest.raises(ValueError, match="no pack 'q'"):
        packager.evidence(tmp_path, ["q"])


def test_the_zip_holds_what_the_brief_asks_for_and_not_the_teams_working_material():
    """01_data, 02_src, 03_assets, requirements.txt, README.md — and pyproject.toml, which
    requirements.txt installs from. The plans, research and process documents, the tooling
    and its tests stay in the repository."""
    ships = ["README.md", "requirements.txt", "pyproject.toml", "02_src/adii/tools/sql.py",
             "02_src/adii/demo/web/app.js", "02_src/tests/architecture/test_boundaries.py",
             "01_data/incidents/revenue-drop-03df8b/world.sql",
             "01_data/walkthrough/record.json", "01_data/demo/csv/README.md",
             "02_src/docs/architecture.md", "02_src/docs/evaluation_report.md",
             "02_src/scripts/check_env.py", "02_src/scripts/admissibility_square.py",
             "02_src/scripts/evaluation_report.py",
             "03_assets/identity/assets/logo/adii-symbol.svg"]
    stays = ["CLAUDE.md", "AGENTS.md", "TEAM.md", ".gitignore", ".gitattributes",
             ".env.example", ".github/workflows/ci.yml", ".claude/skills/x/SKILL.md",
             "02_src/docs/final_plan.md", "02_src/docs/inherited/CONFORMANCE.md",
             "02_src/docs/contributing.md", "02_src/scripts/guard_check.py",
             "02_src/scripts/package_submission.py", "02_src/scripts/sync_status.py",
             "02_src/tests/architecture/test_guard_check.py",
             "02_src/tests/integration/test_the_submission_zip.py",
             "01_data/packs/pilot-paid-v1.json", "01_data/runs/MANIFEST.json",
             "01_data/demo/world/README.md", "03_assets/archive/front-door-v1/web/app.js",
             "03_assets/identity/DESIGN_SYSTEM.md", "03_assets/diagrams/.gitkeep",
             "studies/openrouter-benchmark/adii_benchmark_v2.py"]
    assert [p for p in ships if not packager.shipped(p)] == []
    assert [p for p in stays if packager.shipped(p)] == []


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


def test_no_shipped_document_points_at_one_that_stays_behind():
    """A judge opens the ZIP, not the repository: a link from a shipped page to a team
    document is a dead link there, and a pointer to what was deliberately kept back."""
    import re
    import subprocess
    root = SCRIPT.parents[2]
    listed = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            cwd=root, capture_output=True, text=True, check=True).stdout.split()
    ships = {p for p in listed if packager.shipped(p)}
    dead = []
    for page in sorted(p for p in ships if p.endswith(".md")):
        text = (root / page).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", text):
            if "://" in target:
                continue
            resolved = (Path(page).parent / target).as_posix()
            resolved = str(Path(resolved)).replace("\\", "/")
            parts = []
            for part in resolved.split("/"):
                if part == "..":
                    parts.pop()
                elif part not in ("", "."):
                    parts.append(part)
            path = "/".join(parts)
            if path not in ships and not any(s.startswith(path + "/") for s in ships):
                dead.append(f"{page} → {target}")
    assert not dead, dead
