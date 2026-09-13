"""Answer keys, oracles and scoring truth belong to the evaluation authority — and to its
package, `02_src/adii/evaluation/`, which the investigator can never import. A copy anywhere
else in this repository is reachable from the runtime.

The rule is a location, not a marker. A file that calls itself a fixture is still a copy of
the truth if it sits where the runtime can read it, so no declaration exempts a file.

The front-door invariants I1 and I2 from docs/DATA_WORLD_v0.md used to be asserted here over
five hand-authored demo fixtures. Those are gone: the inspector shows archived runs and
nothing else, and I1 and I2 are asserted over runs against the operational world once it
exists.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ("02_src", "adii", "evaluation")
MARKERS = ("answer_key", "expected_disposition", "evidence_sufficient",
           "revenue_oracle", "accepted_repair_ids", "canonical_root_cause_id")


def test_evaluation_shaped_data_lives_only_with_the_evaluation_authority():
    for path in ROOT.rglob("*.json"):
        if any(part in (".git", "node_modules", ".venv") for part in path.parts):
            continue
        relative = path.relative_to(ROOT)
        if relative.parts[:3] == AUTHORITY:
            continue
        hits = [m for m in MARKERS if m in path.read_text(encoding="utf-8", errors="ignore")]
        assert not hits, (
            f"{relative} contains {hits}. Evaluation truth lives in "
            f"{'/'.join(AUTHORITY)} and nowhere the runtime can reach.")
