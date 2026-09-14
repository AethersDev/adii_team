"""One command, one incident, one archived run, one report.

    python -m adii.runtime --incident demo-learning-001 --provider fake

`fake` scripts the investigator and the validator from the walkthrough's recorded run — no
model runs and no validator exists yet — and drives them through the real runtime over the
real tool layer, against the walkthrough world. The record that lands in the archive was
produced, not assembled, and its observations are what the tools actually returned. A real
provider is a later unit and arrives with a receipt written first (plan D-11, D-15).

Exit codes, one per way a run can end:
    0  a decision was archived          3  the loop ended the run without a decision; archived
    1  the label is taken               4  an infrastructure failure; archived, traceback on stderr
    2  usage: unknown incident, or a label the archive cannot hold
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ..examples.walkthrough import load
from ..reporting import render_run, write_record
from ..reporting.record import ARCHIVE, reserve
from ..tools import build_sql_tools, open_walkthrough_world
from .fakes import scripted
from .run import run_incident


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.runtime", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--incident", required=True, help="the incident id to investigate")
    parser.add_argument("--provider", required=True, choices=["fake"],
                        help="fake: a scripted investigator and validator over the real "
                             "tool layer — no model, no cost")
    parser.add_argument("--label", help="archive label (default: <incident>-<UTC time>); "
                                        "a label names one run forever")
    parser.add_argument("--archive", default=str(ARCHIVE), metavar="DIR",
                        help="archive root (default: 01_data/runs)")
    parser.add_argument("--no-report", action="store_true",
                        help="archive only; do not print the report")
    args = parser.parse_args(argv)

    context, recorded = load()           # today the walkthrough holds the only incident
    if args.incident != context.incident_id:
        print(f"no such incident {args.incident!r}; "
              f"the only incident today is {context.incident_id!r}")
        return 2
    investigator, _, validator = scripted(recorded)
    tools = build_sql_tools(open_walkthrough_world())
    label = args.label or f"{context.incident_id}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    archive = Path(args.archive)
    try:                          # every precondition that needs no I/O has passed: claim the label
        reserve(archive, label)
    except ValueError as bad:                # the label is not one the archive can hold
        print(f"not archived: {bad}")
        return 2
    except FileExistsError as taken:
        print(f"not archived: {taken}")
        return 1

    record = run_incident(label, context, investigator, tools, validator,
                          configuration={"provider": args.provider, "model": None,
                                         "tools": list(tools.names)})
    print(f"archived {write_record(record, archive)}")
    if not args.no_report:
        print(render_run(record))
    if record.termination == "submitted":
        return 0
    print(f"the run ended without a decision — {record.termination}: {record.detail}")
    return 4 if record.termination == "infrastructure_failure" else 3


if __name__ == "__main__":
    raise SystemExit(main())
