"""Build the submission ZIP from a tagged commit, and the evidence the commit cannot hold.

    python 02_src/scripts/package_submission.py --ref freeze-2026-09-24 \\
        --packs final-sol final-luna final-gpt-4-1 final-held-out

The ZIP is what is qualified on clean Windows and macOS machines (final plan, decision CI,
7.5), so it is built from the tag and never from the working copy: `git archive` of `--ref`,
plus, for each named pack, its receipt and report under 01_data/packs and every run folder
it archived under 01_data/runs — the evidence, which git ignores. Inside, SUBMISSION.json
lists every file with its sha256, the ref and the packs. Timestamps are fixed, so the same
inputs build the same bytes. Standard library only; it reads the repository and writes
adii_submission.zip, nothing else.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EPOCH = (1980, 1, 1, 0, 0, 0)          # the earliest time a ZIP entry can carry
NAME = "SUBMISSION.json"


def tree(tar: bytes) -> dict[str, bytes]:
    """The regular files of a `git archive --format=tar` stream, by path."""
    with tarfile.open(fileobj=io.BytesIO(tar)) as archive:
        return {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}


def evidence(root: Path, packs: list[str]) -> dict[str, bytes]:
    """Each pack's receipt and reports, and every run folder its receipt names a cell of."""
    found: dict[str, bytes] = {}
    for pack in packs:
        receipt = root / "01_data" / "packs" / f"{pack}.json"
        if not receipt.is_file():
            raise ValueError(f"no pack {pack!r}: {receipt.relative_to(root)} is missing")
        for path in sorted((root / "01_data" / "packs").glob(f"{pack}.*")):
            found[path.relative_to(root).as_posix()] = path.read_bytes()
        for folder in sorted((root / "01_data" / "runs").glob(f"{pack}-*")):
            for path in sorted(p for p in folder.rglob("*") if p.is_file()):
                found[path.relative_to(root).as_posix()] = path.read_bytes()
    return found


def package(files: dict[str, bytes], ref: str, packs: list[str]) -> bytes:
    """The ZIP: every file at a fixed time, in path order, and the manifest of them."""
    manifest = {"schema": "adii.submission/v1", "ref": ref, "packs": packs,
                "files": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(files.items())}}
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zipped:
        for path, data in [*sorted(files.items()),
                           (NAME, (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))]:
            entry = zipfile.ZipInfo(path, EPOCH)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            zipped.writestr(entry, data)
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ref", required=True, help="the tag the ZIP is built from")
    parser.add_argument("--packs", nargs="*", default=[], help="packs whose evidence to include")
    parser.add_argument("--out", default=str(ROOT / "adii_submission.zip"))
    args = parser.parse_args(argv)
    try:
        tar = subprocess.run(["git", "archive", "--format=tar", args.ref], cwd=ROOT,
                             capture_output=True, check=True).stdout
    except subprocess.CalledProcessError as refused:     # no such ref, or not a repository
        print(f"git archive {args.ref} failed: {refused.stderr.decode(errors='replace').strip()}")
        return 2
    try:
        files = {**tree(tar), **evidence(ROOT, args.packs)}
    except ValueError as missing:
        print(missing)
        return 2
    data = package(files, args.ref, args.packs)
    Path(args.out).write_bytes(data)
    print(f"wrote {args.out}: {len(files)} files, {len(data) / 1e6:.1f} MB, "
          f"sha256 {hashlib.sha256(data).hexdigest()[:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
