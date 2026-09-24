"""The controlled benchmark: every labelled incident, every arm, every repeat, one pack.

    python -m adii.evaluation.grid --pack rehearsal-1 --provider local --model M \
        --endpoint http://127.0.0.1:8090/v1 --served-as default_model
    python -m adii.evaluation.grid --pack final-1 --provider openai --model gpt-4.1 \
        --max-cost-usd 0.50 --pack-cap-usd 60
    python -m adii.evaluation.grid --pack final-1 --report       # the report, from the records

The question it answers (inherited CONTROLS.md): does investigating change what the agent
decides? Three arms on the same incidents, the same model, the same protocol and bounds —
full (the tool surface), alert-only (no tool: it decides from the alert) and always-escalate
(no model) — each repeated, every cell a run through the runtime's own entry point, archived
under `<pack>-<incident>-<arm>-r<k>`, and scored against the incident's frozen key and
grounding key. A cell that already has a record is not run again, so a pack resumes; a cell
that failed is an archived record like any other, never a missing one.

Spending is capped twice: each paid run by `--max-cost-usd`, hard in the provider; and the
pack by `--pack-cap-usd`, hard by construction — a pack whose every paid run spending its
whole cap, and the judge asked once per paid run at its own bound, would cross it is
refused before anything runs, in exact arithmetic. The pack's receipt,
`01_data/packs/<pack>.json`, is written before the first run and names what the pack is; a
pack resumed with anything different is refused. The report reads the records and the
evaluation reports and nothing else.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from ..examples.canonical_world import incident_id, written
from ..provider import REASONING_EFFORTS
from ..provider.judge import MAX_COST_USD as JUDGE_MAX_COST_USD
from ..provider.judge import Judge
from ..reporting.record import ARCHIVE, LABEL, REPO, read_record, source_revision
from ..runtime import __main__ as runtime
from . import lock
from .__main__ import NAME as REPORT
from .__main__ import score, write_report
from .freeze import load_frozen_answer_key

CATALOGUE = Path(__file__).resolve().parent / "catalogue"
PACKS = REPO / "01_data" / "packs"
TIER = {incident_id(f, s, v): ("explicit" if f.explicit else "implicit")
        for f, s, v in written()}
# incidents found invalid as measurements: kept, frozen, never in a pack unless named
BURNED = frozenset(json.loads((CATALOGUE / "burned.json").read_text(encoding="utf-8"))
                   ["incidents"])
# the live cases, registered before any final run: which a pack runs, by name (decision E)
PARTITION = {k: v for k, v in json.loads((CATALOGUE / "partition.json").read_text(
    encoding="utf-8")).items() if isinstance(v, list)}


def cells(pack: dict) -> list[tuple[str, str, str, int]]:
    """(label, incident, arm, repeat) for every run the pack promises, in running order."""
    return [(f"{pack['pack']}-{incident}-{arm}-r{k}", incident, arm, k)
            for incident in pack["incidents"] for arm in pack["arms"]
            for k in range(1, pack["repeats"] + 1)]


def run_cell(pack: dict, label: str, incident: str, arm: str, archive: Path) -> int:
    argv = ["--incident", incident, "--label", label, "--archive", str(archive), "--no-report",
            "--arm", arm, "--requested-from", f"the grid runner, pack {pack['pack']}"]
    if arm == "always-escalate":
        return runtime.main([*argv, "--provider", "none"])
    argv += ["--provider", pack["provider"], "--model", pack["model"],
             "--max-turns", str(pack["max_turns"])]
    if pack.get("endpoint"):
        argv += ["--endpoint", pack["endpoint"]]
    if pack.get("served_as"):
        argv += ["--served-as", pack["served_as"]]
    if pack["provider"] == "openai":
        argv += ["--max-cost-usd", str(pack["max_cost_usd"]), "--max-tokens",
                 str(pack["max_tokens"])]
    if pack.get("reasoning_effort"):
        argv += ["--reasoning-effort", pack["reasoning_effort"]]
    return runtime.main(argv)


def report(pack: dict, archive: Path) -> dict:
    """What the pack's records and evaluation reports say, and nothing else."""
    runs = []
    for label, incident, arm, k in cells(pack):
        folder = archive / label
        record = read_record(folder / "record.json") if (folder / "record.json").is_file() \
            else None
        scored = json.loads((folder / REPORT).read_text(encoding="utf-8")) \
            if (folder / REPORT).is_file() else None
        key = load_frozen_answer_key(CATALOGUE / f"{incident}.answer.json")
        runs.append({
            "label": label, "incident": incident, "arm": arm, "repeat": k,
            "truth": key["correct_disposition"], "tier": TIER.get(incident, "other"),
            "termination": record.termination if record else "missing",
            "disposition": record.decision.disposition.value if record and record.decision
            else None,
            # a run with no evaluation report is unscored, never filed as how it ended
            "category": scored["category"] if scored else "unscored" if record else "missing",
            "decisive": (scored.get("grounding") or {}).get("decisive", {}).get("observed")
            if scored else None,
            "validation": record.validation.state if record and record.validation else None,
            "admissible": record.admissible if record else None,
            "cost_usd": record.api_cost_usd if record else 0.0,
            "latency_ms": record.latency_ms if record else None})
    right = ("success", "correct_abstention")
    arms = {}
    for arm in pack["arms"]:
        mine = [r for r in runs if r["arm"] == arm]
        arms[arm] = {
            "runs": len(mine),
            "right": sum(r["category"] in right for r in mine),
            "right_by_truth": {t: f"{sum(r['category'] in right for r in mine if r['truth'] == t)}"
                                  f"/{sum(r['truth'] == t for r in mine)}"
                               for t in ("REPAIR", "NO_REPAIR", "ESCALATE")},
            "right_by_tier": {t: f"{sum(r['category'] in right for r in mine if r['tier'] == t)}"
                                 f"/{sum(r['tier'] == t for r in mine)}"
                              for t in ("explicit", "implicit")},
            "categories": dict(Counter(r["category"] for r in mine)),
            "decisive_observed": sum(bool(r["decisive"]) for r in mine),
            # admitted (authorized and accepted) where the key says no repair was right; a
            # wrong repair admitted on a REPAIR incident is in the categories, not here
            "admitted_where_no_repair_was_right": sum(bool(r["admissible"])
                                                      and r["truth"] != "REPAIR" for r in mine),
            "cost_usd_lower_bound": round(sum(r["cost_usd"] for r in mine), 4)}
    split = defaultdict(set)
    for r in runs:
        split[(r["incident"], r["arm"])].add(r["disposition"])
    return {"schema": "adii.benchmark_report/v1", "pack": pack["pack"], "arms": arms,
            "unscored": [r["label"] for r in runs if r["category"] in ("unscored", "missing")],
            "repeat_disagreements": sorted(f"{i} {a}: {sorted(map(str, d))}"
                                           for (i, a), d in split.items() if len(d) > 1),
            "runs": runs}


def markdown(result: dict) -> str:
    lines = [f"# Benchmark {result['pack']}", "",
             "| arm | right | REPAIR | NO_REPAIR | ESCALATE | explicit | implicit | decisive "
             "evidence seen | admitted where no repair was right | cost, lower bound |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for arm, a in result["arms"].items():
        t, tier = a["right_by_truth"], a["right_by_tier"]
        lines.append(f"| {arm} | {a['right']}/{a['runs']} | {t['REPAIR']} | {t['NO_REPAIR']} | "
                     f"{t['ESCALATE']} | {tier['explicit']} | {tier['implicit']} | "
                     f"{a['decisive_observed']}/{a['runs']} | "
                     f"{a['admitted_where_no_repair_was_right']} | "
                     f"${a['cost_usd_lower_bound']} |")
    lines += ["", "Runs not scored: " + (", ".join(result["unscored"]) or "none"),
              "", "Repeats that disagreed: "
              + (", ".join(result["repeat_disagreements"]) or "none"), ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.evaluation.grid", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--report", action="store_true", help="only write the report")
    parser.add_argument("--provider", choices=["local", "openai"])
    parser.add_argument("--model")
    parser.add_argument("--endpoint")
    parser.add_argument("--served-as")
    parser.add_argument("--arms", nargs="+", default=list(runtime.ARMS),
                        choices=list(runtime.ARMS))
    parser.add_argument("--repeats", type=int, default=3)
    # demo is the stage's and superseded is kept only as history: neither is ever a pack
    parser.add_argument("--partition", choices=("benchmark", "held_out"), default="benchmark",
                        help="the registered set a pack runs (catalogue/partition.json)")
    parser.add_argument("--incidents", nargs="+",
                        help="named incidents instead of a partition: a rehearsal's, never a "
                             "final pack's")
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--max-cost-usd", type=float, default=0.50)
    parser.add_argument("--max-tokens", type=int, default=1024,
                        help="the completion bound per request on a paid provider: room for a "
                             "decision with its patch, priced in full in every reserve")
    parser.add_argument("--reasoning-effort", choices=REASONING_EFFORTS,
                        help="a reasoning model's effort, a pack term like every bound")
    parser.add_argument("--pack-cap-usd", type=float)
    parser.add_argument("--judge-model", help="a priced model for cases the key's ids cannot "
                                              "settle; without it they are reported unresolved")
    parser.add_argument("--archive", default=str(ARCHIVE))
    parser.add_argument("--packs", default=str(PACKS))
    args = parser.parse_args(argv)
    args.incidents = args.incidents or PARTITION[args.partition]
    if not LABEL.fullmatch(args.pack):
        print(f"--pack {args.pack!r} must be one label segment")
        return 2
    receipt, archive = Path(args.packs) / f"{args.pack}.json", Path(args.archive)
    if args.report:
        pack = json.loads(receipt.read_text(encoding="utf-8"))
    else:
        if not (args.provider and args.model) or args.repeats < 1:
            print("--provider, --model and at least one repeat are needed to run a pack")
            return 2
        if args.reasoning_effort and args.provider != "openai":
            print("--reasoning-effort is a paid reasoning model's setting: --provider openai")
            return 2
        pack = {"schema": "adii.pack/v1", "pack": args.pack, "provider": args.provider,
                "model": args.model, "endpoint": args.endpoint, "served_as": args.served_as,
                "arms": args.arms, "repeats": args.repeats, "incidents": args.incidents,
                "max_turns": args.max_turns, "max_cost_usd": args.max_cost_usd,
                "max_tokens": args.max_tokens,
                "pack_cap_usd": args.pack_cap_usd, "judge_model": args.judge_model,
                # a term only when set, so a pack begun before the term existed resumes
                **({"reasoning_effort": args.reasoning_effort} if args.reasoning_effort
                   else {})}
        if args.pack in lock.PACKS:
            # a registered final pack runs on the newest freeze, as it was frozen, or not at all
            freeze = lock.newest()
            moved = lock.drift(freeze) if freeze else None
            if freeze is None or moved or pack != freeze["packs"].get(args.pack):
                print(f"{args.pack} is a registered final pack: it runs only on the newest "
                      "freeze, unchanged, with its frozen terms — " + (
                          "no freeze has been taken" if freeze is None else
                          f"{len(moved)} frozen file(s) changed since {freeze['name']}" if moved
                          else "these terms differ from the frozen ones"))
                return 2
            pack["freeze"] = {"name": freeze["name"], "digest": freeze["digest"]}
        paid = sum(arm != "always-escalate" for _, _, arm, _ in cells(pack))
        if args.provider == "openai" or args.judge_model:     # a judge is priced either way
            judged = JUDGE_MAX_COST_USD if args.judge_model else Decimal(0)
            per_run = Decimal(str(args.max_cost_usd)) if args.provider == "openai" else Decimal(0)
            worst = paid * (per_run + judged)
            if args.pack_cap_usd is None or worst > Decimal(str(args.pack_cap_usd)):
                print(f"the pack's worst case is {paid} paid runs × (${per_run:.2f}"
                      f" + a judge's ${judged:.2f}) = ${worst:.2f}; --pack-cap-usd must be at "
                      "least that, or the pack smaller")
                return 2
        if receipt.is_file():
            was = json.loads(receipt.read_text(encoding="utf-8"))
            if {k: v for k, v in was.items() if k not in ("created_at", "source_revision")} \
                    != pack | {"schema": was.get("schema")}:
                print(f"{receipt} names a different pack; a pack resumes only as it began")
                return 2
        else:
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text(json.dumps({**pack, "created_at": datetime.now(UTC).isoformat(
                timespec="seconds"), "source_revision": source_revision()}, indent=2) + "\n",
                encoding="utf-8", newline="\n")
        judge = Judge(args.judge_model) if args.judge_model else None
        for label, incident, arm, _ in cells(pack):
            folder = archive / label
            if not (folder / "record.json").is_file():
                if folder.exists():
                    print(f"{label}: reserved and unfinished; left as it is")
                    continue
                run_cell(pack, label, incident, arm, archive)
            if (folder / "record.json").is_file() and not (folder / REPORT).is_file():
                try:
                    write_report(folder, score(folder, CATALOGUE / f"{incident}.answer.json",
                                               CATALOGUE / f"{incident}.grounding.json", judge))
                except ValueError as why:          # e.g. a repair nobody could check
                    print(f"{label}: not scored — {why}")
    result = report(pack, archive)
    (Path(args.packs) / f"{args.pack}.report.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    (Path(args.packs) / f"{args.pack}.report.md").write_text(markdown(result) + "\n",
                                                             encoding="utf-8", newline="\n")
    print(markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
