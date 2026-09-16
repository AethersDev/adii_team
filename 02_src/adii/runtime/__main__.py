"""One command, one incident, one archived run, one report.

    python -m adii.runtime --incident demo-learning-001 --provider scripted

`scripted` replays the investigator and the validator from the walkthrough's recorded run — no
model runs and no validator exists yet — and drives them through the real runtime over the
real tool layer, against the walkthrough world. The record that lands in the archive was
produced, not assembled, and its observations are what the tools actually returned.

    python -m adii.runtime --incident orders-missing-day --provider local \
        --endpoint http://127.0.0.1:11434/v1 --model llama3.1

`local` (SPIKE) drives A's real investigator loop with a model behind an OpenAI-compatible
endpoint on this machine — Ollama, LM Studio, mlx_lm.server — over the real tool layer,
against the walkthrough world or a development specimen's. Nothing is paid for and no
receipt is needed; a paid provider waits for plan D-15 and D-12. No validator exists yet,
so a live REPAIR carries a verdict that says exactly that: not checked, therefore not
accepted, and no finding about the repair.

Exit codes, one per way a run can end:
    0  a decision was archived          3  the loop ended the run without a decision; archived
    1  the label is taken               4  an infrastructure failure; archived, traceback on stderr
    2  usage: unknown incident, or a label the archive cannot hold
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from ..examples.specimens import SPECIMENS
from ..examples.walkthrough import load
from ..reporting import render_run, write_record
from ..reporting.receipts import digest_of, write_receipt
from ..reporting.record import ARCHIVE, reserve
from ..tools import ReadOnlyDatabase, build_sql_tools, open_walkthrough_world
from ..tools.walkthrough_world import build_script
from .run import Recorder, run_incident
from .scripted import replay

WALKTHROUGH_WORLD = build_script()


def incident(incident_id: str):
    """The incident's context, a fresh tool layer over its world, the world's digest, and
    the walkthrough's recorded run if this is the walkthrough. None when no such incident
    exists."""
    context, recorded = load()
    if incident_id == context.incident_id:
        return (context, build_sql_tools(open_walkthrough_world()),
                digest_of(WALKTHROUGH_WORLD), recorded)
    for specimen in SPECIMENS:
        if specimen.context.incident_id == incident_id:
            tools = build_sql_tools(ReadOnlyDatabase.in_memory(specimen.world))
            if specimen.extra_tool:
                tools.register(*specimen.extra_tool)
            return specimen.context, tools, digest_of(specimen.world), None
    return None


def artefacts(context, world_digest: str) -> dict[str, str]:
    """What the run is about to expose to a model, by digest: the incident as handed over
    and the world behind the tools. The evaluation authority's frozen identifiers join
    these when a run is scored."""
    handed = json.dumps({"incident_id": context.incident_id, "alert": context.alert,
                         "as_of": context.as_of,
                         "permitted_write_paths": list(context.permitted_write_paths)},
                        sort_keys=True)
    return {"incident": digest_of(handed), "world": world_digest}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.runtime", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--incident", required=True, help="the incident id to investigate")
    parser.add_argument("--provider", required=True, choices=["scripted", "local"],
                        help="scripted: a scripted investigator and validator over the real "
                             "tool layer — no model, no cost. local: A's loop with a model "
                             "behind a local OpenAI-compatible endpoint (SPIKE)")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/v1",
                        help="local only: the OpenAI-compatible base URL (default: Ollama's)")
    parser.add_argument("--model", help="local only: the model's identity, as the record keeps it")
    parser.add_argument("--served-as", metavar="NAME",
                        help="local only: the name the endpoint wants in requests when it differs "
                             "from --model (mlx-lm's server: default_model)")
    parser.add_argument("--max-turns", type=int, default=12,
                        help="local only: the model-turn bound (default 12)")
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
    context, tools, world_digest, recorded = found
    if args.provider == "scripted":
        if recorded is None:
            print(f"the scripted provider replays the walkthrough only; {args.incident!r} has no "
                  "recorded run — use --provider local, or python -m adii.examples.specimens")
            return 2
        configuration = {"provider": "scripted", "model": None, "tools": list(tools.names)}
        reason = "scripted replay of a recorded run: no model, nothing is spent"
    else:
        if not args.model:
            print("--provider local needs --model <id the endpoint serves>")
            return 2
        configuration = {"provider": "local", "model": args.model, "endpoint": args.endpoint,
                         "served_as": args.served_as, "max_turns": args.max_turns,
                         "tools": list(tools.names),
                         "execution_mode": "live", "cost_basis": "local endpoint, no price"}
        reason = (f"a local model, {args.model}, at {args.endpoint}: no nominal price, "
                  "nothing is spent")
    label = args.label or f"{context.incident_id}-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"
    archive = Path(args.archive)
    try:                          # every precondition that needs no I/O has passed: claim the label
        folder = reserve(archive, label)
    except ValueError as bad:                # the label is not one the archive can hold
        print(f"not archived: {bad}")
        return 2
    except FileExistsError as taken:
        print(f"not archived: {taken}")
        return 1
    # The receipt, before anything is spent: written and flushed, kept on every path.
    write_receipt(folder, label=label, artefacts=artefacts(context, world_digest),
                  configuration=configuration, reason=reason)
    # Every event lands in trace.jsonl the moment it happens: the live view of the run, and
    # what a killed run leaves behind. The record written at the end is the authority.
    recorder = Recorder(sink=folder / "trace.jsonl")
    if args.provider == "scripted":
        investigator, _, validator = replay(recorded)
    else:
        from .live import LoopInvestigator, NoValidatorYet  # the spike
        investigator = LoopInvestigator(endpoint=args.endpoint, model=args.model,
                                        max_turns=args.max_turns, recorder=recorder,
                                        served_as=args.served_as)
        validator = NoValidatorYet()

    record = run_incident(label, context, investigator, tools, validator,
                          configuration=configuration, recorder=recorder)
    print(f"archived {write_record(record, archive)}")
    if not args.no_report:
        print(render_run(record))
    if record.termination == "submitted":
        return 0
    print(f"the run ended without a decision — {record.termination}: {record.detail}")
    return 4 if record.termination == "infrastructure_failure" else 3


if __name__ == "__main__":
    raise SystemExit(main())
