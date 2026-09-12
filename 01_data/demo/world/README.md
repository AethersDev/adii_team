# The canonical demo world

**Not built yet. This directory is a work order.**

It is also the first operational environment the whole team shares: the tool layer
exposes it, the agent loop investigates it, the evaluation layer knows its truth
independently, and telemetry renders it. Until it exists, every part of the system is
working against fixtures or fakes, and nothing has been integrated.

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

Generate the front-door fixtures from this world rather than hand-authoring them, and
retire the current evaluation-derived ones in `../fixtures/`. Each generated fixture
declares `provenance: "generated"`; a test asserts every fixture declares how it was made.

The orientation layer should render actual output from a runnable world, not a curated
story that resembles one.
