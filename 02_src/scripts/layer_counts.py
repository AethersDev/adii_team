"""What the checks caught, by layer, in every run of one pack — counted from its records.

    python 02_src/scripts/layer_counts.py --pack local-qwen3-4b

Registered with that pack, before its first run (02_src/docs/qwen_local_extension.md). A
refusal is counted under the check that fired, as the record names it, never reclassified:

    protocol     the loop refused a malformed tool call or decision        corrective
    evidence     the loop refused a citation of something never observed   corrective
    entitlement  the authorizer denied a proposed fix                      terminal
    validity     the validator rejected a proposed fix, naming its checks  terminal

A corrective check tells the model why and lets it try again within its bounds; a terminal
one tells it nothing. A run is unaided when no corrective check fired. A tool refusing its
arguments is the tool's answer, an observation, not a check. Beside the layers: how many
fixes were proposed, how many a terminal check refused, and how many both authorities
admitted. Nothing here scores a run: whether a decision was right is the grid's report, from
the frozen keys.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "02_src"))
from adii.contracts import Disposition  # noqa: E402
from adii.evaluation.grid import PACKS, cells  # noqa: E402
from adii.investigator.loop import INVALID_TOOL_CALL, TOOL_CALL_THEN_TEXT  # noqa: E402
from adii.reporting.record import ARCHIVE, RunRecord, read_record  # noqa: E402

LAYERS = (("protocol", "corrective"), ("evidence", "corrective"),
          ("entitlement", "terminal"), ("validity", "terminal"))


def fired(record: RunRecord) -> Counter:
    """The checks that fired in one run, by layer."""
    count = Counter()
    for event in record.trace:
        if event.kind == "decision_rejected":
            count["evidence" if event.payload["rejection_class"] == "evidence_gate"
                  else "protocol"] += 1
        elif event.kind == "tool_result" and event.payload["status"] == "REJECTED" and \
                event.payload["content"].get("error") in (INVALID_TOOL_CALL, TOOL_CALL_THEN_TEXT):
            count["protocol"] += 1
    if record.authorization is not None and not record.authorization.authorized:
        count["entitlement"] += 1
    if record.validation is not None and record.validation.state == "REJECT":
        count["validity"] += 1
    return count


def summary(pack: dict, archive: Path) -> str:
    runs = {label: read_record(archive / label / "record.json")
            for label, *_ in cells(pack) if (archive / label / "record.json").is_file()}
    counts = {label: fired(record) for label, record in runs.items()}
    promised = len(cells(pack))
    lines = [f"# What the checks caught: {pack['pack']}", "",
             f"{len(runs)} of {promised} promised runs have a record.", "",
             "| layer | kind | refusals | runs where it fired |", "|---|---|---|---|"]
    for layer, kind in LAYERS:
        lines.append(f"| {layer} | {kind} | {sum(c[layer] for c in counts.values())} | "
                     f"{sum(c[layer] > 0 for c in counts.values())}/{len(runs)} |")
    unaided = sum(not (c["protocol"] or c["evidence"]) for c in counts.values())
    fixes = [label for label, record in runs.items()
             if record.decision is not None and record.decision.disposition is Disposition.REPAIR]
    refused = sum(bool(counts[label]["entitlement"] or counts[label]["validity"])
                  for label in fixes)
    endings = Counter(record.termination for record in runs.values())
    lines += ["", f"Unaided runs: {unaided}/{len(runs)}.",
              f"Fixes proposed: {len(fixes)}; refused by a terminal check: {refused}; admitted: "
              f"{sum(runs[label].admissible for label in fixes)}.",
              "Endings: " + ", ".join(f"{k} {v}" for k, v in sorted(endings.items())) + ".", "",
              "Runs where a check fired: " + (", ".join(
                  f"`{label}` ({', '.join(f'{k} {v}' for k, v in sorted(c.items()))})"
                  for label, c in counts.items() if c) or "none") + "."]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pack", required=True)
    parser.add_argument("--archive", default=str(ARCHIVE))
    parser.add_argument("--packs", default=str(PACKS))
    args = parser.parse_args(argv)
    pack = json.loads((Path(args.packs) / f"{args.pack}.json").read_text(encoding="utf-8"))
    print(summary(pack, Path(args.archive)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
