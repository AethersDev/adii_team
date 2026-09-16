"""Manifest-first preservation of the run archive — inherited D13.

    python -m adii.reporting.manifest                  # attest: write 01_data/runs/MANIFEST.json
    python -m adii.reporting.manifest --verify [DIR]   # hold a directory to its manifest alone
    python -m adii.reporting.manifest --preserve DEST  # attest, copy, re-verify the copy

Three mechanisms, never confused: hygiene (the ignore rule keeps payloads out of history),
attestation (a tracked manifest of what exists: path, size, digest, retention), and
preservation (a second copy verified against the manifest made *before* the copy). Ignoring
is not preserving. A copy verified only against itself is a second chance to have the same
corruption twice, so the manifest is written first and both sides are held to it.

The original is never deleted here, on any outcome. Deleting it on the strength of a copy
is a decision for whoever holds the verified copy, and this module refuses to make it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .record import ARCHIVE, source_revision

SCHEMA = "adii.archive_manifest/v1"
NAME = "MANIFEST.json"
# Every record is evidence of a run and is kept; a class that may be rebuilt from recorded
# identifiers, or kept only as diagnostics, is declared here when such an artefact exists.
RETENTION = "evidence"


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def attest(root: Path) -> dict:
    """The manifest of `root` as it is now: one entry per archived record."""
    entries = [{"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size,
                "digest": digest(path), "retention": RETENTION}
               for path in sorted(root.glob("*/record.json"))]
    return {"schema": SCHEMA, "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_revision": source_revision(), "entries": entries}


def write_manifest(root: Path) -> Path:
    path = root / NAME
    path.write_text(json.dumps(attest(root), indent=2) + "\n", encoding="utf-8", newline="\n")
    return path


@dataclass(frozen=True)
class Verification:
    checked: int
    missing: tuple[str, ...]
    altered: tuple[str, ...]
    unlisted: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not (self.missing or self.altered or self.unlisted)


def verify(root: Path, manifest: dict | None = None) -> Verification:
    """Hold `root` to a manifest — its own tracked one by default — from the manifest alone:
    every listed file present at the listed size and digest, and nothing archived that the
    manifest does not list. Absence is a finding, not an exemption."""
    if manifest is None:
        manifest = json.loads((root / NAME).read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError(f"unknown manifest schema {manifest.get('schema')!r}")
    listed = {e["path"]: e for e in manifest["entries"]}
    missing, altered = [], []
    for rel, entry in listed.items():
        path = root / rel
        if not path.is_file():
            missing.append(rel)
        elif path.stat().st_size != entry["bytes"] or digest(path) != entry["digest"]:
            altered.append(rel)
    present = {p.relative_to(root).as_posix() for p in root.glob("*/record.json")}
    return Verification(len(listed), tuple(missing), tuple(altered),
                        tuple(sorted(present - set(listed))))


def preserve(root: Path, destination: Path) -> Verification:
    """Manifest first, then the copy, then the copy held to that manifest."""
    manifest = attest(root)
    destination.mkdir(parents=True, exist_ok=True)
    for entry in manifest["entries"]:
        target = destination / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / entry["path"], target)
    (destination / NAME).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8",
                                    newline="\n")
    return verify(destination, manifest)


def report(what: str, result: Verification) -> None:
    print(f"{what}: {result.checked} listed", end="")
    for name, items in (("missing", result.missing), ("altered", result.altered),
                        ("unlisted", result.unlisted)):
        if items:
            print(f"; {len(items)} {name}: {', '.join(items)}", end="")
    print(". OK" if result.ok else ". FAILED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.reporting.manifest", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", default=str(ARCHIVE), metavar="DIR",
                        help="the archive to attest (default: 01_data/runs)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", nargs="?", const="", metavar="DIR",
                      help="hold DIR (default: the archive) to the manifest inside it")
    mode.add_argument("--preserve", metavar="DEST", help="attest, copy to DEST, verify the copy")
    args = parser.parse_args(argv)
    root = Path(args.archive)
    if args.verify is not None:
        result = verify(Path(args.verify) if args.verify else root)
        report("verified", result)
        return 0 if result.ok else 1
    if args.preserve:
        result = preserve(root, Path(args.preserve))
        report(f"preserved to {args.preserve}", result)
        print("the original is untouched; delete it only on the strength of a verified copy")
        return 0 if result.ok else 1
    path = write_manifest(root)
    print(f"attested {len(attest(root)['entries'])} record(s) in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
