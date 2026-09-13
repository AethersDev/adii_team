"""The team's Hello World.

    python -m adii.examples.walkthrough --step

Walks one complete ADII run, one boundary at a time, using the real contract objects.
Nothing here is a scientific scenario and nothing here is one of the frozen development
incidents: `demo-learning-001` exists only to make the architecture concrete.

If you can narrate this run, you can read the rest of the codebase.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    InvestigationRun,
    TraceEvent,
    ValidationResult,
)
from ..reporting import render_run
from ..reporting.record import RunRecord, write_record

REPO = Path(__file__).resolve().parents[3]
FIXTURE = REPO / "01_data" / "walkthrough"
ARCHIVE = REPO / "01_data" / "runs"


def load() -> tuple[IncidentContext, InvestigationRun]:
    """Read the fixture into contract objects. If a contract invariant is wrong, this
    raises here — which is the point: the fixture is also a test of the contracts."""
    incident = json.loads((FIXTURE / "incident.json").read_text(encoding="utf-8"))
    context = IncidentContext(
        incident_id=incident["incident_id"], alert=incident["alert"],
        as_of=incident["as_of"],
        permitted_write_paths=tuple(incident["permitted_write_paths"]))

    events = tuple(
        TraceEvent(sequence=raw["sequence"], kind=raw["kind"], payload=raw["payload"])
        for raw in map(json.loads, (FIXTURE / "trace.jsonl").read_text(
            encoding="utf-8").splitlines()) if raw)

    raw_decision = json.loads((FIXTURE / "decision.json").read_text(encoding="utf-8"))
    decision = InvestigationDecision(
        disposition=Disposition(raw_decision["disposition"]),
        root_cause_id=raw_decision["root_cause_id"],
        root_cause_summary=raw_decision["root_cause_summary"],
        repair_id=raw_decision["repair_id"], patch=raw_decision["patch"])

    raw_validation = json.loads((FIXTURE / "validation.json").read_text(encoding="utf-8"))
    validation = ValidationResult(
        accepted=raw_validation["accepted"], report=raw_validation["report"],
        checks_run=tuple(raw_validation["checks_run"]))

    executed = sum(1 for e in events if e.kind == "tool_result" and e.payload["status"] == "OK")
    run = InvestigationRun(
        incident_id=context.incident_id, decision=decision, trace=events,
        validation=validation, tool_calls=executed, model_turns=5,
        api_cost_usd=0.0142, latency_ms=8_400)
    return context, run


def stages(context: IncidentContext, run: InvestigationRun) -> list[tuple[str, str]]:
    """(what happens, which object crosses which boundary)."""
    calls = {e.payload["call_id"]: e.payload for e in run.trace if e.kind == "tool_call"}
    results = {e.payload["call_id"]: e.payload for e in run.trace if e.kind == "tool_result"}
    decision = run.decision

    def pair(call_id: str, note: str) -> tuple[str, str]:
        call, result = calls[call_id], results[call_id]
        return (f"{note}\n"
                f"    investigator sends  "
                f"ToolCall(name={call['name']!r}, arguments={call['arguments']})\n"
                f"    tools returns       ToolResult(status={result['status']!r})\n"
                f"              {json.dumps(result['content'])[:120]}",
                "investigator -> ToolCall -> tools ;  tools -> ToolResult -> investigator")

    return [
        (f"An alert arrives. Nobody knows yet whether the pipeline is broken.\n"
         f"    {context.alert}",
         "operator -> IncidentContext -> investigator"),
        (f"The investigator is handed the incident. Note what it is NOT handed:\n"
         f"    no filesystem path, no database handle, no answer key.\n"
         f"    IncidentContext(incident_id={context.incident_id!r}, as_of={context.as_of!r})\n"
         f"    It may write only to: {list(context.permitted_write_paths)}",
         "IncidentContext crosses into the investigator"),
        pair("c1", "First it asks what the data looks like. It does not guess."),
        pair("c2", "Then it checks the SOURCE. Counts are steady at ~300/day."),
        pair("c3", "Then the MART. 2.97 where the source says 297 — a 100x gap."),
        (f"It tries a tool that does not exist. The boundary refuses it.\n"
         f"    investigator sends  ToolCall(name='delete_table', ...)\n"
         f"    tools returns       ToolResult(status='DENIED')\n"
         f"              {json.dumps(results['c4']['content'])}\n"
         f"    The tool layer decides what the investigator may do, and it cannot\n"
         f"    reach past it.",
         "the tool layer is a boundary, not a helper"),
        (f"With the evidence in hand it commits to exactly one disposition.\n"
         f"    InvestigationDecision(disposition={decision.disposition.value},\n"
         f"                          root_cause_id={decision.root_cause_id!r},\n"
         f"                          repair_id={decision.repair_id!r})\n"
         f"    A REPAIR must carry a repair_id AND a patch. The contract enforces it.",
         "investigator -> InvestigationDecision -> validation"),
        (f"The candidate repair goes to the validator — a DIFFERENT authority.\n"
         f"    patch: {list(decision.patch)}\n"
         f"    The agent has its own rehearsal tool and would happily say 'passes'.\n"
         f"    That is a hypothesis. Only the validator returns a verdict.",
         "validation rebuilds from frozen inputs; the investigator never sees how"),
        (f"    ValidationResult(accepted={run.validation.accepted},\n"
         f"                     checks_run={list(run.validation.checks_run)})\n"
         f"    ACCEPT here means the repair was independently reproduced — not that the\n"
         f"    agent convinced itself.",
         "validation -> ValidationResult -> telemetry"),
        (f"Everything observable is persisted as the public run.\n"
         f"    {len(run.trace)} TraceEvents, {run.tool_calls} tool calls, "
         f"{run.model_turns} model turns, ${run.api_cost_usd:.4f}\n"
         f"    tool_calls is counted from the TRACE, never self-reported by the agent.",
         "every component -> TraceEvent -> telemetry"),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step", action="store_true",
                        help="pause between stages (press Enter to advance)")
    parser.add_argument("--report-only", action="store_true", help="print only the report")
    parser.add_argument("--archive", nargs="?", const=str(ARCHIVE), metavar="DIR",
                        help="write this run to the archive as one record, so the inspector "
                             "shows it (default: 01_data/runs)")
    args = parser.parse_args(argv)

    context, run = load()
    if args.archive:
        record = RunRecord.from_run("demo-learning-001", context, run,
                                    configuration={"provider": "fixture", "model": None},
                                    origin="walkthrough")
        try:
            path = write_record(record, Path(args.archive))
        except FileExistsError as taken:
            print(f"not archived: {taken}")
            return 1
        print(f"archived {path}")
        return 0
    if not args.report_only:
        print("=" * 78)
        print("ADII WALKTHROUGH — demo-learning-001 (a teaching fixture, not a scenario)")
        print("=" * 78)
        for number, (body, boundary) in enumerate(stages(context, run), start=1):
            print(f"\n[{number}/9]  {body}\n         ...... {boundary}")
            if args.step:
                try:
                    input("\n         -- Enter to continue --")
                except EOFError:
                    args.step = False
        print("\n" + "=" * 78)
        print("And this is what the telemetry layer renders from it:")
        print("=" * 78 + "\n")
    print(render_run(context, run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
