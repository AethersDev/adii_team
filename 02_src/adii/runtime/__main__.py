"""One command, one incident, one archived run, one report.

    python -m adii.runtime --incident demo-learning-001 --provider fake

`fake` scripts the investigator, the tool layer and the validator from the walkthrough's
recorded run — the only incident that exists today — and drives them through the real
runtime, so the record that lands in the archive was produced, not assembled. A real
provider is a later unit and arrives with a receipt written first (plan D-11, D-15).
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ..examples.walkthrough import load
from ..reporting import RunRecord, render_run, write_record
from ..reporting.record import ARCHIVE
from .fakes import scripted
from .run import run_incident


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.runtime", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--incident", required=True, help="the incident id to investigate")
    parser.add_argument("--provider", required=True, choices=["fake"],
                        help="fake: scripted components — no model, no network, no cost")
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
    investigator, tools, validator = scripted(recorded)
    run = run_incident(context, investigator, tools, validator)

    label = args.label or f"{context.incident_id}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    try:
        record = RunRecord.from_run(label, context, run,
                                    configuration={"provider": args.provider, "model": None},
                                    origin="runtime")
        path = write_record(record, Path(args.archive))
    except ValueError as bad:                # the label is not one the archive can hold
        print(f"not archived: {bad}")
        return 2
    except FileExistsError as taken:
        print(f"not archived: {taken}")
        return 1
    print(f"archived {path}")
    if not args.no_report:
        print(render_run(context, run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
