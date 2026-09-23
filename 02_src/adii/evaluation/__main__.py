"""Score one archived run against a frozen answer key; keep the report beside the record.

    python -m adii.evaluation --run <label> --key PATH [--archive DIR]

The seam between the runtime's record and the evaluation authority, and nothing more: the
record is read through the runtime's own reader, so an unknown schema is refused there
rather than guessed at here; the key must be frozen (`freeze.py`), so what scored the run
can be named by digest; the two must name the same incident; a REPAIR nobody checked,
where the key also says REPAIR, is refused, not scored — there the verdict would decide
between success and rejection, and the runtime's placeholder says "not checked". Where
the key says the right call was not a repair, the disposition alone decides and no
validator is consulted, so an unchecked REPAIR scores as what it is: unwarranted. The
report is written once, never overwritten.
No score is decided here. `build_evaluation_report` decides it, from the record and the
key alone.

Exit status: 0 scored; 1 the run already carries a report; 2 usage, or a run this command
refuses to score — and it says why.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..provider.judge import ENDPOINT as JUDGE_ENDPOINT
from ..provider.judge import Judge
from ..reporting.record import ARCHIVE, LABEL, read_record
from .evaluation_report import build_evaluation_report, to_json
from .freeze import compute_digest, load_frozen_answer_key
from .grounding import load_grounding_key
from .judge import judge_repair

NAME = "evaluation_report.json"


def score(folder: Path, key_path: Path, grounding_path: Path | None = None,
          judge: Judge | None = None) -> dict:
    """The report for one archived run, or ValueError naming why it is not scored. With a
    grounding key — bound by digest to this very answer key — the report's grounding says
    whether the decisive observations were made and cited. With a judge, a case the
    deterministic path cannot settle is put to it, and the report names the judge by model
    and prompt digest beside `settled_by`; without one, that case stays unresolved."""
    record = json.loads(read_record(folder / "record.json").to_json())
    key = load_frozen_answer_key(key_path)
    incident = record["context"]["incident_id"]
    if key["incident_id"] != incident:
        raise ValueError(f"the key is for {key['incident_id']!r}; this run investigated "
                         f"{incident!r} — a run is scored against its own incident's key only")
    verdict = record["validation"]
    # not checked (the legacy placeholder) or not checkable (no rebuildable world, in
    # structure): either way the validation side is not established, and where the key
    # says REPAIR it is what decides between success and rejection
    unchecked = verdict is not None and not verdict["accepted"] and not verdict["checks_run"]
    if unchecked and key["correct_disposition"] == "REPAIR":
        raise ValueError("the repair was never checked (checks_run is empty" +
                         (f"; reason_code {verdict['reason_code']}" if verdict.get("reason_code")
                          else "") + ") and the key says REPAIR: an unestablished verdict is "
                         "not a rejection, so this run is not scored until a validator has run")
    grounding = None
    if grounding_path is not None:
        grounding = load_grounding_key(grounding_path, answer_key_dir=key_path.parent)
        if grounding["answer_key_filename"] != key_path.name:
            raise ValueError(f"the grounding key is bound to {grounding['answer_key_filename']!r}, "
                             f"not to {key_path.name!r}: a run is grounded against its own key")
    asked: list[dict] = []

    def judged(decision: dict, validation: dict, answer_key: dict) -> dict:
        result = judge_repair(decision, validation, answer_key, judge)
        asked.append(result)
        return result

    report = build_evaluation_report(record, key, judge=judged if judge else None,
                                     grounding_key=grounding)
    if report.get("settled_by") == "judge":        # which judge said what, for this case
        [result] = asked
        report["judge"] = {**judge.calls[-1], "verdict": result["verdict"],
                           "justification": result["reasoning"]}
    return report


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
    parser.add_argument("--grounding-key", metavar="PATH",
                        help="a grounding key bound to --key: whether the decisive observations "
                             "were made and cited, beside the category")
    parser.add_argument("--judge-model", metavar="ID",
                        help="a priced model that settles what the deterministic path cannot: a "
                             "correct, accepted repair whose ids differ from the key's; without "
                             "it such a case is reported unresolved")
    parser.add_argument("--judge-endpoint", default=JUDGE_ENDPOINT, metavar="URL",
                        help=f"the judge's OpenAI-compatible endpoint (default {JUDGE_ENDPOINT})")
    parser.add_argument("--archive", default=str(ARCHIVE), metavar="DIR",
                        help="the archive (default: 01_data/runs)")
    args = parser.parse_args(argv)
    folder = Path(args.archive) / args.run
    if not LABEL.fullmatch(args.run) or not (folder / "record.json").is_file():
        print(f"no archived run {args.run!r} in {args.archive}")
        return 2
    key_path = Path(args.key)
    try:
        judge = Judge(args.judge_model, args.judge_endpoint) if args.judge_model else None
        report = score(folder, key_path,
                       Path(args.grounding_key) if args.grounding_key else None, judge)
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
          + f", settled by {report.get('settled_by', 'none')}"
          + f" — against {key_path.name} sha256:{compute_digest(key_path)}")
    print(f"  report: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
