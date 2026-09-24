"""The admissibility square, as four archived runs: works and allowed, allowed but does not
work, works but not allowed, and a patch the data cannot take (final plan, 7.1 and 4.5).

    python 02_src/scripts/admissibility_square.py

The deck's proof of the authorities is records, never a slide's claim, and no model is
asked to misbehave on cue: four scripted proposals on the demo company's fix case go through
the real runtime — the tool layer, the authorizer in `run_incident`, the validator on the
live path — and each lands in 01_data/runs as a receipt, a trace and a record like any run.
The proposals are scripted and say so in the receipt; the verdicts are the authorities'.
Only from the frozen commit: the tree must match the newest freeze, and each label carries
the freeze's name, so a square is generated once per freeze. No model, no key, $0.
It is not the evaluated system: it lives outside the frozen trees and changes nothing there.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from adii.contracts import Disposition, InvestigationDecision
from adii.evaluation import lock
from adii.evaluation.scale import Ideal, ideal, scale_to_the_total
from adii.examples.canonical_world import DEMO, INCIDENTS, incident_id, staging
from adii.reporting.receipts import write_receipt
from adii.reporting.record import ARCHIVE, reserve, write_record
from adii.runtime.__main__ import alerted_series, artefacts, incident
from adii.runtime.live import ValidatorOnLivePath
from adii.runtime.run import Recorder, run_incident
from adii.validation.patching import path_of
from adii.validation.validator import Validator

CASE = incident_id(DEMO, "transform-defect")      # the stage's fix case, run in no pack
STG, MART = path_of("stg_orders"), path_of("mart_daily_revenue")


def proposals() -> dict[str, InvestigationDecision]:
    """The four cells, each a REPAIR on the same diagnosis; only the patch differs."""
    _, right = ideal(DEMO, "transform-defect")
    mart = Validator().frozen_inputs(CASE)[1]["mart_daily_revenue"]
    wrong = replace(right, repair_id="SCALE_THE_DAY_UP",
                    patch={STG: scale_to_the_total(DEMO.day, staging(DEMO, "transform-defect"))})
    assert right.disposition is Disposition.REPAIR and list(right.patch) == [STG]
    return {
        "admissible": right,                                  # permitted · ACCEPT
        "hides-the-symptom": wrong,                           # permitted · REJECT by the oracle
        "not-allowed": replace(right, patch={**right.patch, MART: mart}),   # denied · ACCEPT
        "cannot-apply": replace(right, repair_id="READ_A_TABLE_THAT_IS_NOT_THERE",
                                patch={STG: "SELECT * FROM no_such_table"}),  # REJECT, rebuild
    }


def square(archive: Path, freeze: str) -> list[Path]:
    """Archive the four runs under `archive`, labelled square-<freeze>-<cell>."""
    calls, _ = ideal(DEMO, "transform-defect")
    written = []
    for cell, decision in proposals().items():
        context, tools, world_digest, _, evidence = incident(CASE)
        label = f"square-{freeze}-{cell}"
        folder = reserve(archive, label)
        configuration = {"provider": "scripted", "model": None, "tools": list(tools.names),
                         "proposal": cell, "freeze": freeze}
        write_receipt(folder, label=label, artefacts=artefacts(context, world_digest, evidence),
                      configuration=configuration,
                      reason=f"the admissibility square, cell {cell}: a scripted proposal "
                             "judged by the real authorizer and validator; no model, nothing "
                             "is spent")
        recorder = Recorder(sink=folder / "trace.jsonl")
        try:
            record = run_incident(label, context, Ideal(calls, decision), tools,
                                  ValidatorOnLivePath(), configuration=configuration,
                                  recorder=recorder, alert=alerted_series(INCIDENTS / CASE))
        finally:
            recorder.close()
        written.append(write_record(record, archive))
    return written


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args(argv)
    freeze = lock.newest()
    if freeze is None:
        print("no freeze has been taken: the square is generated from the frozen commit only")
        return 2
    moved = lock.drift(freeze)
    if moved:
        print(f"the tree no longer matches {freeze['name']}: {', '.join(moved[:10])}")
        return 2
    try:
        for path in square(ARCHIVE, freeze["name"]):
            print(f"archived {path.parent.name}")
    except FileExistsError as taken:          # this freeze's square exists; labels are forever
        print(taken)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
