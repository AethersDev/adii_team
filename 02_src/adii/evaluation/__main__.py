"""Score one archived run against a frozen answer key; keep the report beside the record.

    python -m adii.evaluation --run <label> --key PATH [--archive DIR]

The seam between the runtime's record and the evaluation authority, and nothing more: the
record is read through the runtime's own reader, so an unknown schema is refused there
rather than guessed at here; the key must be frozen (`freeze.py`), so what scored the run
can be named by digest; the two must name the same incident; a REPAIR nobody checked is
refused, not scored — the runtime's placeholder verdict says "not checked", and only a
validator's verdict is a rejection; and the report is written once, never overwritten.
No score is decided here. `build_evaluation_report` decides it, from the record and the
key alone.

Exit status: 0 scored; 1 the run already carries a report; 2 usage, or a run this command
refuses to score — and it says why.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..reporting.record import ARCHIVE, LABEL, read_record
from .evaluation_report import build_evaluation_report, to_json
from .freeze import compute_digest, load_frozen_answer_key

NAME = "evaluation_report.json"


def score(folder: Path, key_path: Path) -> dict:
    """The report for one archived run, or ValueError naming why it is not scored."""
    record = json.loads(read_record(folder / "record.json").to_json())
    key = load_frozen_answer_key(key_path)
    incident = record["context"]["incident_id"]
    if key["incident_id"] != incident:
        raise ValueError(f"the key is for {key['incident_id']!r}; this run investigated "
                         f"{incident!r} — a run is scored against its own incident's key only")
    verdict = record["validation"]
    if verdict is not None and not verdict["accepted"] and not verdict["checks_run"]:
        raise ValueError("the repair was never checked (checks_run is empty): a placeholder "
                         "verdict is not a rejection, so this run is not scored until a "
                         "validator has run")
    return build_evaluation_report(record, key)


def write_report(folder: Path, report: dict) -> Path:
    path = folder / NAME
    if path.exists():
        raise FileExistsError(f"{path} exists: a run is scored once; a rescoring is a new "
                              "report under a new key version, never an overwrite")
    path.write_text(to_json(report), encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.evaluation", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, metavar="LABEL", help="the archived run")
    parser.add_argument("--key", required=True, metavar="PATH",
                        help="the frozen answer key (its .sha256 beside it)")
    parser.add_argument("--archive", default=str(ARCHIVE), metavar="DIR",
                        help="the archive (default: 01_data/runs)")
    args = parser.parse_args(argv)
    folder = Path(args.archive) / args.run
    if not LABEL.fullmatch(args.run) or not (folder / "record.json").is_file():
        print(f"no archived run {args.run!r} in {args.archive}")
        return 2
    key_path = Path(args.key)
    try:
        report = score(folder, key_path)
    except (ValueError, FileNotFoundError) as why:   # not scorable, or the key is not frozen
        print(f"not scored: {why}")
        return 2
    try:
        path = write_report(folder, report)
    except FileExistsError as taken:
        print(str(taken))
        return 1
    print(f"scored {args.run}: {report['category']}"
          + (f" ({report['sub_kind']})" if report.get("sub_kind") else "")
          + f" — against {key_path.name} sha256:{compute_digest(key_path)}")
    print(f"  report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
