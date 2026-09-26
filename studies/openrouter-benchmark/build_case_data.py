"""Build ./adii_case_data/ from the six real ADII specimens in
`adii.examples.specimens`, so a custom evaluation harness gets genuine ADII worlds and a
genuine answer key — not hand-transcribed data that can drift from the source.

    python 02_src/scripts/build_case_data.py

Writes, under the repository's parent directory (`../adii_case_data/`, alongside
`adii_team/`):

  cases/tools_manifest.json         the two core tools' JSON schemas (get_schema, run_sql)
  cases/case_NN_<incident_id>/incident.json   the alert, as_of and permitted write paths
  cases/case_NN_<incident_id>/data/*.csv      every table of that specimen's world, as CSV
  evaluation/expected.json          per case: {case_id, incident_id, disposition, root_cause}
  evaluation/ground_truth.jsonl     one line per case, the same fields

Ground truth here is the specimen's own scripted decision (`Run.decision`, or the first
run's when a specimen has several) — the disposition the specimens author committed the
record to, not a claim independently re-derived. Say so plainly wherever this data is used.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "02_src"))

from adii.examples.specimens import SPECIMENS  # noqa: E402
from adii.tools import ReadOnlyDatabase  # noqa: E402
from adii.tools.sql_tools import GET_SCHEMA, RUN_SQL  # noqa: E402

OUT = REPO.parent / "adii_case_data"


def tool_schema(spec) -> dict[str, object]:
    return spec.to_json_schema()


def ground_truth_of(specimen) -> tuple[str, str | None, str]:
    """The disposition, root_cause_id and root_cause_summary of a specimen's answer key: the
    first run that reached a decision (a specimen with more than one run keeps later runs
    for other endings — a bound, a rejection, a model failure — which carry no decision of
    their own)."""
    for run in specimen.runs:
        if run.decision is not None:
            d = run.decision
            return d.disposition.value, d.root_cause_id, d.root_cause_summary
    raise ValueError(f"{specimen.context.incident_id}: no run carries a decision")


def write_case(index: int, specimen) -> dict[str, object]:
    case_id = f"case_{index:02d}_{specimen.context.incident_id}"
    folder = OUT / "cases" / case_id
    data_dir = folder / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    incident = {
        "incident_id": specimen.context.incident_id,
        "case_id": case_id,
        "alert": specimen.context.alert,
        "as_of": specimen.context.as_of,
        "permitted_write_paths": list(specimen.context.permitted_write_paths),
    }
    (folder / "incident.json").write_text(
        json.dumps(incident, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    world = ReadOnlyDatabase.in_memory(specimen.world)
    for table in world.tables():
        result = world.query(f'SELECT * FROM "{table}"', max_rows=100_000)
        path = data_dir / f"{table}.csv"
        with path.open("w", encoding="utf-8", newline="") as sink:
            writer = csv.writer(sink, lineterminator="\n")
            writer.writerow(result.columns)
            writer.writerows([["" if v is None else v for v in row] for row in result.rows])

    disposition, root_cause_id, root_cause_summary = ground_truth_of(specimen)
    return {
        "case_id": case_id,
        "incident_id": specimen.context.incident_id,
        "disposition": disposition,
        "root_cause_id": root_cause_id,
        "root_cause_summary": root_cause_summary,
    }


def main() -> int:
    cases_dir = OUT / "cases"
    eval_dir = OUT / "evaluation"
    cases_dir.mkdir(parents=True, exist_ok=True)
    eval_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"tools": [tool_schema(GET_SCHEMA), tool_schema(RUN_SQL)]}
    (cases_dir / "tools_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    keys = []
    for i, specimen in enumerate(SPECIMENS, start=1):
        keys.append(write_case(i, specimen))
        print(f"wrote case_{i:02d}_{specimen.context.incident_id}")

    (eval_dir / "expected.json").write_text(
        json.dumps(keys, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (eval_dir / "ground_truth.jsonl").open("w", encoding="utf-8", newline="\n") as sink:
        for row in keys:
            sink.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n{len(keys)} cases written under {cases_dir}")
    print(f"ground truth written under {eval_dir}")
    print("\nSource of truth: adii_team/02_src/adii/examples/specimens.py — hand-authored "
          "development specimens, scripted (no model ran to produce them), carrying no "
          "independent evaluation claim. Treat 'ground truth' here as the specimens' own "
          "authored decision, not an externally audited answer key.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
