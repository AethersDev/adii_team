"""Write the ten case specimens as incident packages the ADII runtime loads with --incident-dir.

    python build_benchmark_incidents.py

Each package under benchmark_incidents/<incident_id>/: incident.json + world.sql (from
adii.examples.case_specimens) + a transform bundle holding a placeholder for every permitted
write path, so the runtime's readable_or_refused rule admits the incident.

Kept outside adii_team/01_data/incidents on purpose: packages there must come from the team
generator with a frozen answer key (test_incident_packages_are_ready). Refuses to overwrite.

Note for D: the placeholders are not the real transform sources. Until they are replaced,
REPAIR decisions on these incidents patch a file whose real content the model never saw.
"""
import json
import sys
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO.parent  # the workspace beside the repo: case data, incidents and results stay out of it
sys.path.insert(0, str(REPO / "02_src"))

from case_specimens import SPECIMENS  # beside this script  # noqa: E402

INCIDENTS = ROOT / "benchmark_incidents"
PLACEHOLDER = ("-- [Auto-generated mock file for ADII Benchmark by Jouri - "
               "D: Please replace with real context later]\n")


def main() -> None:
    for specimen in SPECIMENS:
        ctx = specimen.context
        folder = INCIDENTS / ctx.incident_id
        if folder.exists():
            raise SystemExit(f"refusing to overwrite {folder}")
        (folder / "transform_sources").mkdir(parents=True)
        incident = {"incident_id": ctx.incident_id, "alert": ctx.alert, "as_of": ctx.as_of,
                    "permitted_write_paths": list(ctx.permitted_write_paths)}
        (folder / "incident.json").write_text(json.dumps(incident, indent=2) + "\n",
                                              encoding="utf-8")
        (folder / "world.sql").write_text(specimen.world, encoding="utf-8")
        mapping = {}
        for path in ctx.permitted_write_paths:
            target = PurePosixPath(path)
            mapping[target.stem] = target.name
            (folder / "transform_sources" / target.name).write_text(PLACEHOLDER, encoding="utf-8")
        (folder / "transform_map.json").write_text(json.dumps(mapping, indent=2) + "\n",
                                                   encoding="utf-8")
        print("wrote", folder.name, mapping)


if __name__ == "__main__":
    main()
