# The canonical demo world

**Not built yet. This directory is a work order.**

It is also the first operational environment the whole team shares: the tool layer
exposes it, the agent loop investigates it, the evaluation layer knows its truth
independently, and telemetry renders it. Until it exists, the investigator and the
validator are scripted from the walkthrough; the tool layer is real, and the runtime
drives it over the walkthrough's tiny world (`02_src/adii/tools/walkthrough_world.py`), so
the first integration exists — against the teaching incident only.

Specification: [DATA_WORLD_v0.md](../../../02_src/docs/DATA_WORLD_v0.md) — *The canonical
demo world*.

Build the smallest executable operational world in which three configurations of one alert
(*revenue down 45%*) resolve three different ways, legibly. Same organisation, same
schema, same alert family, same tool vocabulary; only the causal state differs:

| | expected | delivered | loaded | pipeline | other evidence |
|---|---:|---:|---:|---|---|
| **A** | 100 | 100 | 55 | **FAILED** at row 55 | the transform that stopped, readable |
| **B** | 56 | 56 | 56 | SUCCESS | an operational notice: the promotion ended yesterday |
| **C** | 100 | ? | 55 | SUCCESS | a manifest that disagrees with the load; the source receipt unavailable |

What each configuration *means* is not written here, on purpose. This folder is what the
investigator may read, and the rule above it stands: no file in `01_data/` states a
disposition. The evaluation authority (`02_src/adii/evaluation/`) can establish one for
each configuration independently, and a development key may live there under its rules;
a key for an unseen evaluation never ships in the repository at all.

Fifty to a hundred rows. The value is in the relationships between evidence sources, not
volume. Each configuration is one incident package in the format the runtime already
loads (`incident.json`, `world.sql`, and the evidence bundles `--incident-dir` keeps:
transform, notice, change history, reconciliation, declared schema); no demo-specific
transport is invented for it.

## What "done" means

1. All three configurations instantiate the same operational schema.
2. Every investigator-visible fact is reachable only through the controlled evidence
   surface (`02_src/adii/tools/`).
3. No investigator-visible artefact states or encodes the expected disposition.
4. The evaluation authority can independently establish one disposition for each
   configuration.
5. **A** carries sufficient operational evidence to identify a candidate change — and the
   validator can rebuild the world with that change applied.
6. **B** carries sufficient evidence to establish that the observed change is legitimate
   without inventing a fault.
7. **C** establishes a real anomaly while withholding the evidence a repair would need.
8. The runtime executes all three with no configuration-specific code.
9. The page renders archived run records only; it has no A/B/C truth logic.

## Then, and only then

Run the investigator against this world and archive the runs. The inspector shows archived
runs and nothing else, so the front door renders actual output from a runnable world, not a
curated story that resembles one. The front-door invariants I1 and I2 in
[DATA_WORLD_v0.md](../../../02_src/docs/DATA_WORLD_v0.md) are then asserted over those
runs.
