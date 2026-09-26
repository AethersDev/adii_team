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
    contracts          234 lines
    investigator       368 lines
    tools             1251 lines
    validation         247 lines
    evaluation        1474 lines
    reporting          683 lines
    runtime            818 lines
    examples           880 lines
    demo               407 lines
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
