# Current status

**Generated. Do not edit.** `python 02_src/scripts/sync_status.py` rewrites it,
and a test fails the build when it is stale. Milestone marks come from
[build_plan.md](build_plan.md); what is built comes from looking at the code.

## Milestones

```text
    [x]  M0 — Everybody can run the repo            6/6
    [x]  M1 — Basic agent loop                      5/5
    [x]  M2 — Controlled tool use                   6/6
    [>]  M3 — Multi-step investigation              2/4
    [ ]  M4 — Structured terminal decision          2/4
    [ ]  M5 — Candidate repair and escalation       0/3
    [x]  M6 — Independent validation                4/4
    [ ]  M7 — End-to-end vertical slice             7/9
    [ ]  M8 — Reliability and failure handling      2/4
    [ ]  M9 — Freeze                                0/3
    [ ]  M10 — Unseen evaluation                    0/3
```

## What exists

```text
    contracts          216 lines
    investigator       340 lines
    tools             1230 lines
    validation         217 lines
    evaluation        1341 lines
    reporting          647 lines
    runtime            728 lines
    examples           592 lines
    demo               439 lines
```

## Scaffold only — a README and an empty package

```text
    (none)
```

## Verification

```bash
python 02_src/scripts/check_env.py
pytest
python -m ruff check 02_src
python -m adii.examples.walkthrough
python -m adii.demo
```
