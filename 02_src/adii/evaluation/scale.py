"""The scale ladder: the canonical world's exact incidents, grown, and the same decisions.

    python -m adii.evaluation.scale                         # 10k, 100k and 1M orders
    python -m adii.evaluation.scale --rows 10000 5000000    # any sizes

Decision quality is measured on incidents; capacity on rows. This measures capacity: one
family's three worlds regenerated at each size — the same causal facts, the same ids, so the
same frozen keys — each investigated through the real runtime and tool layer by the ideal
investigator below, the correct repair and the scale-to-the-total fake put through the real
validator, and every decision scored against its key. What grows is only the data behind the
tools; what the investigator is shown stays bounded. Sizes run smallest first in one process,
and a process's peak memory only rises, so each size's reading is its own peak (reported where
the platform says it; not on Windows).

The ideal investigator lives here, with the evaluation authority, because it knows the
answers: the calls a careful investigator makes and the decision each world's key labels.
The generator knows none of it.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import tempfile
import time
from pathlib import Path

from ..contracts import Disposition, InvestigationDecision, ToolCall
from ..examples import canonical_world as cw
from ..runtime.__main__ import incident_from_dir
from ..runtime.run import run_incident
from ..validation.patching import path_of
from ..validation.validator import Validator
from .evaluation_report import build_evaluation_report
from .freeze import load_frozen_answer_key
from .grounding import load_grounding_key

CATALOGUE = Path(__file__).resolve().parent / "catalogue"
STG = path_of("stg_orders")
STAGE_EVERY_ORDER = "SELECT order_id, order_date, distributor, amount_usd FROM raw_orders"


def scale_to_the_total(day) -> str:
    """The fake: the day's revenue scaled up to what arrived, the missing orders still missing."""
    acked = ("FROM raw_orders r JOIN load_log l ON l.batch_id = r.batch_id WHERE r.line_no <= "
             "l.rows_loaded")
    return (f"SELECT r.order_id, r.order_date, r.distributor, r.amount_usd * CASE WHEN "
            f"r.order_date = '{day}' THEN (SELECT SUM(amount_usd) FROM raw_orders WHERE "
            f"order_date = '{day}') / (SELECT SUM(r.amount_usd) {acked} AND r.order_date = "
            f"'{day}') ELSE 1 END AS amount_usd {acked}")


def ideal(family: cw.Family, state: str):
    """The calls a careful investigator makes, and the decision the key labels."""
    day, batch = family.day, f"B-{family.day:%m%d}"
    calls = {
        "load-stopped": [("run_sql", {"query": "SELECT batch_id, rows_received, rows_loaded, "
                                               f"status FROM load_log WHERE run_date = '{day}'"}),
                         ("get_transform", {"transform_id": "stg_orders"})],
        "business-changed": [("run_sql", {"query": "SELECT distributor, COUNT(*) FROM raw_orders "
                                                   f"WHERE order_date = '{day}' GROUP BY "
                                                   "distributor"})],
        "cannot-decide": [("run_sql", {"query": "SELECT * FROM delivery_manifest WHERE batch_id "
                                                f"= '{batch}'"}),
                          ("read_reconciliation", {"reconciliation_id": "vendor-receipts"})],
    }[state]
    decision = {
        "load-stopped": InvestigationDecision(
            Disposition.REPAIR, "LOAD_STOPPED_PARTWAY", "The load stopped part-way.",
            "STAGE_EVERY_DELIVERED_ORDER", {STG: STAGE_EVERY_ORDER}),
        "business-changed": InvestigationDecision(
            Disposition.NO_REPAIR, "DISTRIBUTOR_CONTRACTS_ENDED", "The drop is real."),
        "cannot-decide": InvestigationDecision(
            Disposition.ESCALATE, None, "The evidence cannot decide between the two."),
    }[state]
    return calls, decision


class Ideal:
    """Makes the calls, then commits the decision citing what the tool layer minted."""

    def __init__(self, calls, decision) -> None:
        self._calls, self._decision = calls, decision

    def investigate(self, context, tools):
        seen = [tools.execute(ToolCall(f"i{n}", name, args))
                for n, (name, args) in enumerate(self._calls)]
        return dataclasses.replace(self._decision, evidence_refs=tuple(
            r.content["evidence_id"] for r in seen if r.ok))


def scored(record, case: str) -> dict:
    key = load_frozen_answer_key(CATALOGUE / f"{case}.answer.json")
    grounding = load_grounding_key(CATALOGUE / f"{case}.grounding.json")
    return build_evaluation_report(json.loads(record.to_json()), key, grounding_key=grounding)


def measure(rows: int) -> dict:
    """One size, in this process: the first family's three worlds at `rows` orders."""
    family = dataclasses.replace(cw.FAMILIES[0], per_day=rows // (cw.HISTORY + 1))
    out: dict = {"rows": rows, "states": {}}
    with tempfile.TemporaryDirectory() as tmp:
        for state in cw.STATES:
            case = cw.incident_id(family, state)
            folder = Path(tmp) / case
            began = time.perf_counter()
            for name, text in cw.package(family, state).items():
                (folder / name).parent.mkdir(parents=True, exist_ok=True)
                (folder / name).write_text(text, encoding="utf-8", newline="\n")
            generated = time.perf_counter() - began
            began = time.perf_counter()
            context, tools, *_ = incident_from_dir(folder)
            built = time.perf_counter() - began
            validator = Validator(incidents=Path(tmp))
            began = time.perf_counter()
            record = run_incident("scale", context, Ideal(*ideal(family, state)), tools,
                                  validator, configuration={"provider": "scripted"})
            investigated = time.perf_counter() - began
            report = scored(record, case)
            row = {"package_mb": round(sum(p.stat().st_size for p in folder.rglob("*")
                                           if p.is_file()) / 1e6, 1),
                   "generate_s": round(generated, 2), "build_s": round(built, 2),
                   "investigate_s": round(investigated, 2),
                   "disposition": record.decision.disposition.value if record.decision else None,
                   "category": report["category"],
                   "decisive": report["grounding"]["decisive"]["observed"],
                   "statuses": sorted({e.payload["status"] for e in record.trace
                                       if e.kind == "tool_result"})}
            if state == "load-stopped":
                row["validation"] = record.validation.state
                decision = InvestigationDecision(Disposition.REPAIR, None, "fake", "F",
                                                 {STG: scale_to_the_total(family.day)})
                began = time.perf_counter()
                row["fake_repair"] = validator.validate(context, decision).state
                row["validate_s"] = round(time.perf_counter() - began, 2)
            out["states"][state] = row
    try:
        import resource  # not on Windows: memory is then not reported
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        out["peak_rss_mb"] = round(rss / (1e6 if sys.platform == "darwin" else 1e3))
    except ImportError:
        out["peak_rss_mb"] = None
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.evaluation.scale", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=int, nargs="+", default=[10_000, 100_000, 1_000_000])
    parser.add_argument("--out", metavar="FILE", help="also write the results as JSON")
    args = parser.parse_args(argv)
    results = []
    for rows in sorted(args.rows):                  # smallest first: see the module's note
        results.append(measure(rows))
        r = results[-1]
        verdicts = {s: v["category"] for s, v in r["states"].items()}
        a = r["states"]["load-stopped"]
        print(f"{rows:>10,} orders  {a['package_mb']:>7} MB  build {a['build_s']:>5}s  "
              f"investigate {a['investigate_s']:>5}s  validate {a['validate_s']:>5}s  "
              f"fix {a['validation']}  fake {a['fake_repair']}  peak {r['peak_rss_mb']} MB  "
              f"{verdicts}")
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
