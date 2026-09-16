"""One command, one incident, one archived run, one report.

    python -m adii.runtime --incident demo-learning-001 --provider scripted

`scripted` replays the investigator and the validator from the walkthrough's recorded run — no
model runs and no validator exists yet — and drives them through the real runtime over the
real tool layer, against the walkthrough world. The record that lands in the archive was
produced, not assembled, and its observations are what the tools actually returned.

A real provider is a later unit and arrives after the trace event contract is decided,
with a receipt written first (plan D-6b, D-11, D-15).

Exit codes, one per way a run can end:
    0  a decision was archived          3  the loop ended the run without a decision; archived
    1  the label is taken               4  an infrastructure failure; archived, traceback on stderr
    2  usage: unknown incident, or a label the archive cannot hold
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from ..examples.specimens import SPECIMENS
from ..examples.walkthrough import load
from ..reporting import render_run, write_record
from ..reporting.record import ARCHIVE, reserve
from ..tools import ReadOnlyDatabase, build_sql_tools, open_walkthrough_world
from .run import run_incident
from .scripted import replay


def incident(incident_id: str):
    """The incident's context and a fresh tool layer over its world: the walkthrough's, or
    a development specimen's. None when no such incident exists."""
    context, recorded = load()
    if incident_id == context.incident_id:
        return context, build_sql_tools(open_walkthrough_world()), recorded
    for specimen in SPECIMENS:
        if specimen.context.incident_id == incident_id:
            tools = build_sql_tools(ReadOnlyDatabase.in_memory(specimen.world))
            if specimen.extra_tool:
                tools.register(*specimen.extra_tool)
            return specimen.context, tools, None
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.runtime", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--incident", required=True, help="the incident id to investigate")
    parser.add_argument("--provider", required=True, choices=["scripted"],
                        help="scripted: a scripted investigator and validator over the real "
                             "tool layer — no model, no cost")
    parser.add_argument("--label", help="archive label (default: <incident>-<UTC time>); "
                                        "a label names one run forever")
    parser.add_argument("--archive", default=str(ARCHIVE), metavar="DIR",
                        help="archive root (default: 01_data/runs)")
    parser.add_argument("--no-report", action="store_true",
                        help="archive only; do not print the report")
    args = parser.parse_args(argv)

    found = incident(args.incident)
    if found is None:
        known = [load()[0].incident_id, *(s.context.incident_id for s in SPECIMENS)]
        print(f"no such incident {args.incident!r}; known: {', '.join(known)}")
        return 2
    context, tools, recorded = found
    if recorded is None:
        print(f"the scripted provider replays the walkthrough only; {args.incident!r} has no "
              "recorded run — python -m adii.examples.specimens archives its scripted runs")
        return 2
    investigator, _, validator = replay(recorded)
    configuration = {"provider": "scripted", "model": None, "tools": list(tools.names)}
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
                          configuration=configuration)
    print(f"archived {write_record(record, archive)}")
    if not args.no_report:
        print(render_run(record))
    if record.termination == "submitted":
        return 0
    print(f"the run ended without a decision — {record.termination}: {record.detail}")
    return 4 if record.termination == "infrastructure_failure" else 3


if __name__ == "__main__":
    raise SystemExit(main())
