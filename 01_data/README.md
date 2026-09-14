# 01_data — what the system reads

Everything here is **team-visible**. Any teammate, and any evaluator with the ZIP, can
open every file in this folder and should be able to run the system from it.

```text
demo/world/        the operational world the whole team shares
runs/              the archive: one record per run, read by the inspector
walkthrough/       the teaching fixture the walkthrough replays
walkthrough/endings/   the same incident ended every other way, produced by the runtime
```

## What must never be put here

This folder is shipped and it is readable, so anything placed in it is disclosed:

- frozen or unseen evaluation worlds
- answer keys, oracles, or any file that states a correct disposition
- hidden authority state that an investigator is supposed to have to discover
- private research or factory artefacts from any other repository

That is not a filing convention. An investigator that can read the answer has not
investigated anything, and a benchmark whose answers ship with it measures nothing.

A test enforces the sharp edge of this:
`02_src/tests/integration/test_answer_keys_stay_out.py` scans the whole repository for
evaluation-shaped JSON — `answer_key`, `expected_disposition`, `evidence_sufficient` and
friends — and fails the build on any hit outside `02_src/adii/evaluation/`, the evaluation
authority's own package. The rule is a location, not a marker: a file that calls itself a
fixture is still a copy of the truth if it sits where the runtime can read it.

## Adding data

Ask two questions first.

1. **Does the system need it to run?** If it is only needed to grade the system, it does
   not belong in the repository at all.
2. **Would an investigator reading it be cheating?** If yes, it belongs to the evaluation
   authority, not to `01_data/`.

Data changes are reviewed like code. `02_src/docs/DATA_WORLD_v0.md` says who decides what
the operational world contains.
