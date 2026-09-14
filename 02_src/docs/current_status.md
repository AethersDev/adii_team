# Current status

**Generated. Do not edit.** `python 02_src/scripts/sync_status.py` rewrites it,
and a test fails the build when it is stale. Milestone marks come from
[build_plan.md](build_plan.md); what is built comes from looking at the code.

## Milestones

```text
    [x]  M0 — Everybody can run the repo            6/6
    [>]  M1 — Basic agent loop                      0/5
    [ ]  M2 — Controlled tool use                   0/6
    [ ]  M3 — Multi-step investigation              0/4
    [ ]  M4 — Structured terminal decision          0/4
    [ ]  M5 — Candidate repair and escalation       0/3
    [ ]  M6 — Independent validation                0/4
    [ ]  M7 — End-to-end vertical slice             0/4
    [ ]  M8 — Reliability and failure handling      0/4
    [ ]  M9 — Freeze                                0/3
    [ ]  M10 — Unseen evaluation                    0/3
```

## What exists

```text
    contracts          154 lines
    investigator       426 lines
    tools              484 lines
    reporting           69 lines
    examples           128 lines
    demo                86 lines
```

## Scaffold only — a README and an empty package

```text
    validation
    evaluation
```

## Verification

```bash
python 02_src/scripts/check_env.py
pytest
python -m ruff check 02_src
python -m adii.examples.walkthrough
python -m adii.demo
```
