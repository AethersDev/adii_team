# Team

Four people, six weeks, one shared repository, two operating systems.

## How we work

We are four engineers building **one ADII system**. No part of the runtime belongs
exclusively to one person.

Work is assigned as concrete tasks against milestones, not as permanent ownership of a
folder. Anyone may contribute anywhere in the runtime. Every merged contribution must be

- understood by its author,
- tested,
- reviewable by someone who did not write it,
- compatible with the shared architecture.

Cross-review is expected, so knowledge does not end up living in one head.

Two distinctions worth keeping sharp:

```text
task assignee   is not   subsystem owner
reviewer        is not   permanent authority
```

People will naturally get stronger in different parts of the system. That is fine, and it
is a result, not an assignment. The repository does not encode it, because encoding it
before anyone has written a line decides in advance who gets to learn what.

The measure at the end of six weeks is that each of us can say *"I understand and
contributed to the ADII agent end to end"* — not *"I owned the evidence folder"*.

## What the system is made of

Folders organise the system. Tasks organise our work. These are the capabilities a task
names, and a task may name several:

```text
agent-loop     model messages, tool calling, the loop, budgets, stopping
tools          tool schemas, SQL, permissions, the candidate-repair sandbox
state          what the investigation knows so far, and how it got there
evidence       grounding a claim in something that was actually observed
decision       the disposition and the repair proposal committed to
validation     the independent verdict on a proposed repair
evaluation     scoring, baselines, answer keys, what "success" means
telemetry      traces, run artifacts, cost, latency, reproducibility
integration    the end-to-end path through all of the above
```

`02_src/docs/architecture.md` describes what each of these is and where the boundaries
between them are. Those boundaries are enforced by tests, not by who wrote the code.

## Upstream of all of it: the incident world

One decision comes before any implementation and belongs to nobody in particular —
**which operational world ADII lives in**. It is part of the product argument: a world
that cannot produce the same alert from a repairable fault, a legitimate business change,
and insufficient evidence cannot demonstrate what ADII is for, however well it is built.

Four questions the world has to pass:

| | |
|---|---|
| **Legibility** | Does this world make ADII's value legible to a partner in five minutes? |
| **Buildability** | Can it be built cleanly and exposed through a realistic tool surface? |
| **Independence** | Can the correct answer be known independently of the agent, and stay hidden from it? |
| **Reachability** | Can the investigator reach the decisive evidence through permitted tools? |

Whoever implements the world does not choose it alone. A world that is easy to build but
cannot separate the three dispositions has failed, and that failure is invisible from
inside the component that built it.

v0 exists and is frozen — see [02_src/docs/DATA_WORLD_v0.md](02_src/docs/DATA_WORLD_v0.md).
Extend it; do not revise it. Any new incident family needs all four answers before it is
built.

## The six weeks

| Week | Goal | Gate — how we know it happened |
|---|---|---|
| **1** | Runway + the smallest complete loop | A teammate on Windows clones, installs, tests, and runs the walkthrough **without anyone touching their machine**. Then each person explains a *different* section of a live toy run. |
| **2** | The real vertical slice | One command runs incident → investigation → evidence → decision → validation → archived run → readable report. Same commit green on Windows **and** macOS. Fake provider is fine. |
| **3** | Real investigator evidence | One unscored smoke, then development runs. Archived: config, model, trace, decision, validation, usage, cost, latency. We can name concrete failure modes. |
| **4** | The scientific layer | We can answer: *does interactive investigation add measurable value over always-escalate, alert-only, and static evidence?* **"No" is a valid answer.** |
| **5** | Freeze + blind evaluation | Investigator, config, metrics, validator, and authority all frozen. One-shot blind run. No tuning after seeing outcomes. |
| **6** | Analysis, report, demo | A report that shows success, failure, false repair, correct abstention, unnecessary escalation, and repair rejection with equal honesty. |

**The critical path is short.** Everything else happens beside it:

```text
cross-platform repo → contracts → walkable fixture → tiny agent loop
  → vertical slice → real model → dev evaluation → freeze → blind → report
```

If something threatens that line, it gets deprioritised.

## Cadence

- **Monday, 20 min.** Each person: this week's goal, its acceptance test, dependencies,
  likely blocker.
- **Daily, async, 4 lines.** `DONE / NEXT / BLOCKED / PR`.
- **Midweek, 15–30 min.** We *run* `main`. Not slides, not "almost finished".
- **Friday.** Show something the repository could not do last Friday.

## The questions this project keeps returning to

Every design argument here reduces to one of these. They come up in review constantly.

1. The agent requests `run_sql`. Which object crosses which boundary, who executes it, and
   what comes back?
2. The agent's sandbox says its patch passes. Is the repair accepted?
3. Who owns the frozen answer key, when is it consulted, and why would exposing it to the
   agent invalidate everything we report?
4. What terminates the investigation loop?
5. Why is `tool_calls` counted from the trace instead of reported by the agent?
