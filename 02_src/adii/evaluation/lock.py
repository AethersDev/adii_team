"""The freeze: what the final packs run on, named by digest before any of them runs.

    python -m adii.evaluation.lock --name freeze-2026-09-24     # write freezes/<name>.json
    python -m adii.evaluation.lock --check                      # does the tree still match?

Final plan, phase 4. One file per freeze version under `freezes/`, holding the sha256 of
every file the evaluated system is made of — the implementation (every module under
02_src/adii, its protocol, tools, validator, scorer, prices and page), the pinned
requirements, the incident packages, the catalogue (keys, grounding keys, partition, the
burned list) and the oracles — and the terms of every registered final pack (decision E),
written out in full, with the commit it was taken at. The freeze file is committed with the
tree it digests, and the test below proves the two match.

From then on the newest freeze is the contract: a test fails the gate when any frozen file
changes, so an engineering change after the freeze is a new freeze version, never a silent
one (inherited AUTHORITY_LIFECYCLE); and the grid refuses to run a registered pack unless
the tree matches the freeze and the pack's terms are the frozen ones, byte for byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from ..reporting.record import REPO, source_revision

FREEZES = Path(__file__).resolve().parent / "freezes"
PARTITION = json.loads((Path(__file__).resolve().parent / "catalogue" / "partition.json")
                       .read_text(encoding="utf-8"))
SCHEMA = "adii.freeze/v1"
# freeze-YYYY-MM-DD, and -2, -3 … for another version taken the same day: the newest is the
# latest date and, on one date, the highest number — never the last name in sort order
NAME = re.compile(r"freeze-(\d{4}-\d{2}-\d{2})(?:-(\d+))?")
# What the evaluated system is made of: every file under these, and these files.
TREES = ("02_src/adii", "01_data/incidents")
FILES = ("requirements.txt", "pyproject.toml")
SKIPPED = ("__pycache__", ".DS_Store")
FREEZES_DIR = "02_src/adii/evaluation/freezes"     # a freeze does not digest freezes

# The final packs, as decision E registered them: one repeat, twenty turns, a 4,096-token
# completion bound, $0.50 a run and the judge's $0.01 per paid run, judged by gpt-4.1-mini.
COMMON = {"schema": "adii.pack/v1", "provider": "openai", "endpoint": None, "served_as": None,
          "repeats": 1, "max_turns": 20, "max_cost_usd": 0.5, "max_tokens": 4096,
          "judge_model": "gpt-4.1-mini"}
PACKS = {
    "final-sol": {"model": "gpt-6-sol", "reasoning_effort": "low", "partition": "benchmark",
                  "arms": ["full", "alert-only", "always-escalate"], "pack_cap_usd": 12.24},
    "final-luna": {"model": "gpt-6-luna", "reasoning_effort": "low", "partition": "benchmark",
                   "arms": ["full"], "pack_cap_usd": 6.12},
    "final-gpt-4-1": {"model": "gpt-4.1", "partition": "benchmark", "arms": ["full"],
                      "pack_cap_usd": 6.12},
    "final-held-out": {"model": "gpt-6-sol", "reasoning_effort": "low", "partition": "held_out",
                       "arms": ["full"], "pack_cap_usd": 3.06},
}


def terms(name: str) -> dict:
    """A registered pack's terms, in the grid's own receipt shape."""
    spec = dict(PACKS[name])
    partition = spec.pop("partition")
    return {**COMMON, "pack": name, **spec, "incidents": PARTITION[partition]}


def files(root: Path = REPO) -> dict[str, str]:
    """Every frozen file, by repository-relative path, to its sha256."""
    paths = [p for tree in TREES for p in (root / tree).rglob("*")
             if p.is_file() and not any(s in p.parts for s in SKIPPED)
             and not p.relative_to(root).as_posix().startswith(FREEZES_DIR)]
    paths += [root / f for f in FILES]
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths)}


def digest(frozen: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(frozen, sort_keys=True).encode("utf-8")).hexdigest()


def order(path: Path) -> tuple[str, int]:
    date, n = NAME.fullmatch(path.stem).groups()
    return date, int(n or 1)


def newest(root: Path = FREEZES) -> dict | None:
    found = sorted((p for p in root.glob("*.json") if NAME.fullmatch(p.stem)), key=order)
    return json.loads(found[-1].read_text(encoding="utf-8")) if found else None


def drift(freeze: dict, root: Path = REPO) -> list[str]:
    """Every frozen file that changed, appeared or went missing since `freeze`."""
    now, then = files(root), freeze["files"]
    return sorted(p for p in now.keys() | then.keys() if now.get(p) != then.get(p))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.evaluation.lock", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument("--name", help="take a freeze: freeze-<date>, one label segment")
    what.add_argument("--check", action="store_true", help="compare the tree to the newest")
    args = parser.parse_args(argv)
    if args.check:
        freeze = newest()
        if freeze is None:
            print("no freeze has been taken")
            return 2
        moved = drift(freeze)
        print(f"{freeze['name']}: " + ("the tree matches" if not moved else
              f"{len(moved)} frozen file(s) changed: " + ", ".join(moved[:20])))
        return 1 if moved else 0
    if not NAME.fullmatch(args.name):
        print("--name is freeze-YYYY-MM-DD, or freeze-YYYY-MM-DD-2 for another the same day")
        return 2
    path = FREEZES / f"{args.name}.json"
    if path.exists():
        print(f"{path.name} exists: a freeze version is taken once; take a new one")
        return 1
    frozen = files()
    FREEZES.mkdir(exist_ok=True)
    path.write_text(json.dumps({
        "schema": SCHEMA, "name": args.name, "source_revision": source_revision(),
        "taken_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "digest": digest(frozen), "packs": {p: terms(p) for p in PACKS}, "files": frozen,
    }, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(REPO)}: {len(frozen)} files, sha256 {digest(frozen)[:12]}, "
          f"at {source_revision()}")
    print(f"commit it, then tag: git tag {args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
