"""Build the submission ZIP from a tagged commit, and the evidence the commit cannot hold.

    python 02_src/scripts/package_submission.py --ref freeze-2026-09-24 \\
        --packs final-sol final-luna final-gpt-4-1 final-held-out \\
        --runs square-freeze-2026-09-24-admissible square-freeze-2026-09-24-not-allowed ...

The ZIP is what is qualified on clean Windows and macOS machines (final plan, decision CI,
7.5), so it is built from the tag and never from the working copy: `git archive` of `--ref`,
plus, for each named pack, its receipt and report under 01_data/packs and every run folder
it archived under 01_data/runs — the evidence, which git ignores — and each run named by
`--runs` (the admissibility square's, the filmed ones), by exact label. A ZIP holding a `.env`
file, or the first characters of the configured OpenAI key anywhere, is refused, naming only
the files. Timestamps are fixed, so the same inputs build the same bytes.

The ZIP holds what the brief asks for and nothing else: one folder, `ADII_Group05_Code_v1/`,
with 01_data/, 02_src/, 03_assets/, requirements.txt and README.md — and pyproject.toml,
which requirements.txt installs ADII from. Inside those, SHIPPED names what goes, by path
prefix, and LEFT_OUT what does not go from under a shipped prefix: the team's plans,
research and process documents, its tooling and the tests of that tooling stay in the
repository. A file is shipped only if a prefix names it. Every file's sha256 is written
beside the ZIP, never in it, as `ADII_Group05_Code_v1.sha256` in the format
`shasum -a 256 -c` reads: run it next to the extracted folder and each file is checked.
Standard library only; it reads the repository and writes the ZIP and its checksums,
nothing else.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPOCH = (1980, 1, 1, 0, 0, 0)          # the earliest time a ZIP entry can carry
FOLDER = "ADII_Group05_Code_v1"       # the one folder inside, and the ZIP's own name
SHIPPED = (
    "README.md", "requirements.txt", "pyproject.toml", "LICENSE", "LICENSES/",
    "01_data/README.md", "01_data/incidents/", "01_data/walkthrough/", "01_data/demo/csv/",
    "01_data/runs/README.md",
    "02_src/adii/", "02_src/tests/", "02_src/scripts/check_env.py",
    "02_src/scripts/admissibility_square.py", "02_src/scripts/evaluation_report.py",
    "02_src/docs/architecture.md", "02_src/docs/evaluation_report.md",
    "03_assets/README.md", "03_assets/identity/assets/", "03_assets/diagrams/",
    "03_assets/screenshots/",
)
LEFT_OUT = (   # under a shipped prefix, but the team's: tests of its process and tooling
    "02_src/tests/architecture/test_briefing_is_current.py",
    "02_src/tests/architecture/test_status_is_current.py",
    "02_src/tests/architecture/test_documentation_links.py",
    "02_src/tests/architecture/test_guard_check.py",
    "02_src/tests/architecture/test_the_docs_hold.py",
    "02_src/tests/architecture/test_the_frozen_trees_are_committed.py",
    "02_src/tests/integration/test_the_submission_zip.py",
    "02_src/tests/eval_authority/OVERVIEW.md",
)


def shipped(path: str) -> bool:
    """Whether a repository path goes in the ZIP: named by a shipped prefix, not left out,
    and not a placeholder that only keeps an empty folder in git."""
    return (any(path == p or (p.endswith("/") and path.startswith(p)) for p in SHIPPED)
            and path not in LEFT_OUT and Path(path).name != ".gitkeep")


def tree(tar: bytes) -> dict[str, bytes]:
    """The shipped regular files of a `git archive --format=tar` stream, by path."""
    with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
        return {m.name: archive.extractfile(m).read() for m in archive.getmembers()
                if m.isfile() and shipped(m.name)}


def cells(receipt: dict) -> list[str]:
    """The run labels a pack's receipt promises — the grid's own naming, cell by cell."""
    return [f"{receipt['pack']}-{incident}-{arm}-r{k}" for incident in receipt["incidents"]
            for arm in receipt["arms"] for k in range(1, receipt["repeats"] + 1)]


def evidence(root: Path, packs: list[str], runs: list[str] = ()) -> dict[str, bytes]:
    """Each pack's receipt and reports, every run folder its receipt names a cell of, and
    every run named by its exact label."""
    found: dict[str, bytes] = {}
    for label in runs:
        folder = root / "01_data" / "runs" / label
        if not (folder / "record.json").is_file():
            raise ValueError(f"no run {label!r}: {folder.relative_to(root)} holds no record")
        for path in sorted(p for p in folder.rglob("*") if p.is_file()):
            found[path.relative_to(root).as_posix()] = path.read_bytes()
    for pack in packs:
        receipt = root / "01_data" / "packs" / f"{pack}.json"
        if not receipt.is_file():
            raise ValueError(f"no pack {pack!r}: {receipt.relative_to(root)} is missing")
        for path in sorted((root / "01_data" / "packs").glob(f"{pack}.*")):
            found[path.relative_to(root).as_posix()] = path.read_bytes()
        for label in cells(json.loads(receipt.read_text(encoding="utf-8"))):
            folder = root / "01_data" / "runs" / label
            for path in sorted(p for p in folder.rglob("*") if p.is_file()):
                found[path.relative_to(root).as_posix()] = path.read_bytes()
    return found


def configured_key(root: Path) -> str | None:
    """The OpenAI key this machine is configured with — the environment's, else the one line
    of `.env.local` that names it — used only to look for its prefix, never printed."""
    key = os.environ.get("OPENAI_API_KEY")
    env_local = root / ".env.local"
    if not key and env_local.is_file():
        for line in env_local.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"')
    return key or None


def leaks(files: dict[str, bytes], key: str | None) -> list[str]:
    """The files a submission must not carry: any .env file, and any file holding the key's
    first sixteen characters."""
    found = [p for p in files if Path(p).name in (".env", ".env.local")]
    if key and len(key) >= 20:
        found += [p for p, data in files.items() if key[:16].encode() in data]
    return sorted(set(found))


def checksums(files: dict[str, bytes]) -> str:
    """Every file in the ZIP, `<sha256>  <FOLDER>/<path>` a line, in path order: what
    `shasum -a 256 -c` (and `sha256sum -c`) checks against the extracted folder."""
    return "".join(f"{hashlib.sha256(b).hexdigest()}  {FOLDER}/{p}\n"
                   for p, b in sorted(files.items()))


def package(files: dict[str, bytes]) -> bytes:
    """The ZIP: every file at a fixed time, in path order, under the one folder."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path, data in sorted(files.items()):
            entry = zipfile.ZipInfo(f"{FOLDER}/{path}", EPOCH)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            zipped.writestr(entry, data)
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", required=True, help="the tag the ZIP is built from")
    parser.add_argument("--packs", nargs="*", default=[], help="packs whose evidence to include")
    parser.add_argument("--runs", nargs="*", default=[], help="further runs to include, by label")
    # beside the repository, never in it: extracted where it lands, a ZIP inside the checkout
    # is a second copy of the project that the repository's own tests rightly refuse
    parser.add_argument("--out", default=str(ROOT.parent / f"{FOLDER}.zip"))
    args = parser.parse_args(argv)
    try:
        tar = subprocess.run(["git", "archive", "--format=tar", args.ref], cwd=ROOT,
                             capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as refused:     # no such ref, or not a repository
        print(f"git archive {args.ref} failed: {refused.stderr.decode(errors='replace').strip()}")
        return 2
    try:
        files = {**tree(tar), **evidence(ROOT, args.packs, args.runs)}
    except ValueError as missing:
        print(missing)
        return 2
    refused = leaks(files, configured_key(ROOT))
    if refused:
        print("not written: a secret would ship in " + ", ".join(refused))
        return 2
    data = package(files)
    out = Path(args.out)
    out.write_bytes(data)
    listed = out.with_suffix(".sha256")
    listed.write_text(checksums(files), encoding="utf-8", newline="\n")
    print(f"wrote {out}: {len(files)} files, {len(data) / 1e6:.1f} MB, "
          f"sha256 {hashlib.sha256(data).hexdigest()}, from {args.ref}"
          + (f", packs {' '.join(args.packs)}" if args.packs else "")
          + (f", runs {' '.join(args.runs)}" if args.runs else "")
          + f"; each file's sha256 in {listed.name} (shasum -a 256 -c {listed.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
