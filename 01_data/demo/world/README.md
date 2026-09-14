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
(*revenue down 45%*) resolve three different ways, legibly:

| | expected | delivered | loaded | pipeline | other evidence | Correct |
|---|---:|---:|---:|---|---|---|
| **A** | 100 | 100 | 55 | **FAILED** at row 55 | — | **REPAIR** |
| **B** | 56 | 56 | 56 | SUCCESS | promotion ended yesterday | **NO_REPAIR** |
| **C** | 100 | ? | 55 | SUCCESS | manifest fault; source receipt unavailable | **ESCALATE** |




Fifty to a hundred rows. The value is in the relationships between evidence sources, not
volume.

## What "done" means

- **B**: the world is executable and exposed through a realistic tool surface.
- **C**: each configuration's truth is unambiguous and unreachable from the agent.
- **A**: the decisive evidence is reachable through the intended tool path.
- **D**: a new viewer infers each disposition from what is displayed (invariant I1).

## Then, and only then

Run the investigator against this world and archive the runs. The inspector shows archived
runs and nothing else, so the front door renders actual output from a runnable world, not a
curated story that resembles one. The front-door invariants I1 and I2 in
[DATA_WORLD_v0.md](../../../02_src/docs/DATA_WORLD_v0.md) are then asserted over those
runs.
