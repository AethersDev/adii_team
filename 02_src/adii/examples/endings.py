"""The walkthrough incident, ended every other way a run can end.

    python -m adii.examples.endings        # (re)write 01_data/walkthrough/endings/

One record per outcome class besides the walkthrough's own accepted repair: a repair the
validator rejected, a model failure, a bound, and an infrastructure failure. Each is produced
by the runtime — the investigator scripted to end that way, the real tool layer, the
validator scripted — never assembled by hand, so what the report shows is what the runtime
archives. Inherited D11: each has to read as legibly as a success, in its own terms.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..contracts import ToolCall, ToolResult, ValidationResult
from ..reporting import RunRecord, render_run
from ..runtime.fakes import ScriptedValidator, scripted
from ..runtime.run import Terminated, Tools, run_incident
from ..tools import build_sql_tools, open_walkthrough_world
from .walkthrough import FIXTURE, load

ENDINGS = FIXTURE / "endings"


class Ends:
    """An investigator that makes some of the walkthrough's calls, then ends the run."""

    def __init__(self, calls: tuple[ToolCall, ...], ending: Terminated) -> None:
        self._calls, self._ending = calls, ending

    def investigate(self, context, tools):
        for call in self._calls:
            tools.execute(call)
        raise self._ending


class Drops:
    """The tool layer until one call, which the connection does not survive. A call that was
    made and never answered is what the report has to show as unanswered."""

    def __init__(self, inner: Tools, on_call: str) -> None:
        self._inner, self._on_call = inner, on_call

    def execute(self, call: ToolCall) -> ToolResult:
        if call.call_id == self._on_call:
            raise ConnectionError("the warehouse connection dropped")
        return self._inner.execute(call)


def endings() -> dict[str, RunRecord]:
    """The four records, produced now. Deterministic but for provenance and latency."""
    context, recorded = load()
    calls = tuple(ToolCall(e.payload["call_id"], e.payload["name"], e.payload["arguments"])
                  for e in recorded.trace if e.kind == "tool_call")
    investigator, _, accepts = scripted(recorded)
    rejects = ScriptedValidator(ValidationResult(
        accepted=False,
        report="Rebuilt the demo warehouse from frozen inputs with the candidate patch "
               "applied. mart_daily for 2026-01-14 reports 29700.00 against an independently "
               "recomputed 297.00: the patch removes both conversions, not one.",
        checks_run=("pipeline_rebuilds", "row_counts_preserved", "independent_recomputation")))
    cases = {
        "repair-rejected": (investigator, None, rejects),
        "model-failure": (Ends(calls[:1], Terminated(
            "model_failure", "the provider returned an empty message on three attempts")),
            None, accepts),
        "bound-hit": (Ends(calls[:3], Terminated("bound_hit", "tool_calls: 3 of 3 used")),
                      None, accepts),
        "infrastructure-failure": (investigator, "c3", accepts),
    }
    records = {}
    for label, (agent, drop_on, validator) in cases.items():
        tools = build_sql_tools(open_walkthrough_world())
        records[label] = run_incident(
            label, context, agent, Drops(tools, drop_on) if drop_on else tools, validator,
            configuration={"provider": "fake", "model": None, "tools": list(tools.names)})
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--into", default=str(ENDINGS), metavar="DIR",
                        help="where to write (default: 01_data/walkthrough/endings); "
                             "existing files are replaced")
    args = parser.parse_args(argv)
    for label, record in endings().items():
        folder = Path(args.into) / label
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "record.json").write_text(record.to_json(), encoding="utf-8", newline="\n")
        (folder / "report.txt").write_text(render_run(record), encoding="utf-8", newline="\n")
        print(f"wrote {folder / 'record.json'} and report.txt")
    print("(the ConnectionError traceback above is the infrastructure failure being produced; "
          "a real run shows it on stderr the same way)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
