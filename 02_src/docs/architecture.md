# ADII architecture

One diagram. If you understand this, you can read the codebase.

```text
                          INCIDENT
                             │
                             ▼
              ┌──────────────────────────────┐
              │   INVESTIGATOR               │
              │   decides what to look at    │
              └──────────────────────────────┘
                    │  ToolCall      ▲  ToolResult
                    ▼                │
              ┌──────────────────────────────┐
              │   CONTROLLED TOOLS           │
              │   the ONLY way to see data   │
              └──────────────────────────────┘
                             │
                             ▼
              REPAIR   /   NO_REPAIR   /   ESCALATE
                 │
                 └── REPAIR carries a candidate repair
                              │
                              ▼
              ┌──────────────────────────────┐
              │   INDEPENDENT VALIDATION     │
              │   ACCEPT  /  REJECT          │
              └──────────────────────────────┘

  TELEMETRY persists the public run at every step:
      trace → evidence → decision → validation → report

  ══════════════════════════════════════════════════════
   EVALUATION AUTHORITY — we build it here, and it is ours
   incidents, answer keys, scoring
   NEVER part of agent context · never importable by the
   investigator
  ══════════════════════════════════════════════════════
```

## The three authority boundaries

Everything hard about this project is a boundary question. Learn these three.

**1. The agent sees the world only through the tool layer.**
The investigator has no filesystem path, no database handle, no shell. If it could read
files it could read the answer key, and every number we report would be meaningless. The
tool layer is a *boundary*, not a helper: it decides what the investigator may do and
refuses the rest. A `DENIED` result is the boundary working correctly.

**2. The agent is not the validator.**
The investigator has a rehearsal tool and will happily tell itself a patch works. That is
a *hypothesis*. Validation rebuilds from the frozen inputs and returns the *verdict*, and
the investigator never sees how it got there. When someone says "the agent tested the repair and it passed", the answer is:
*candidate testing and independent validation are different authorities.*

**3. The judge is a different program.**
Something has to hold each incident's correct answer, or "correct" is not a measurable
word. That authority — incidents, answer keys, scoring — is the evaluation authority's,
it lives in
`02_src/adii/evaluation/`, and the investigator can never import it. Note it is *not* boundary 2 restated:
validation asks **does this repair work**, the judge asks **was this the right call at
all**. Two questions, two authorities, both unreachable from the investigator.

We build ours. There is no external judge to connect to and nothing to integrate with
later — the prior implementation's scored catalogue is in a private repository, and no
code here imports it.

**4. Authorities have a lifecycle.**
The first three boundaries are about *who may know what*. This one is about *when*. An
authority frozen before it is complete cannot be completed — its hash is the thing that
makes it an authority, and changing the hash invalidates everything scored against it. So
two things that freeze at different times must be two artifacts, bound to each other by
hash rather than merged. This one was learned the hard way; the story is in
[inherited/AUTHORITY_LIFECYCLE.md](inherited/AUTHORITY_LIFECYCLE.md).

## The system's capabilities

One runtime. These are the parts of it, not a list of people.

| Capability | Covers | The question it answers |
|---|---|---|
| **agent-loop** · **state** | the loop, model messages, tool calling, budgets, stopping | How does a model *request* a tool, and what ends the loop? |
| **tools** · **evidence** | schemas, SQL, permissions, candidate-repair sandbox | Why is `DENIED` a success, not a failure? |
| **decision** | the disposition and the repair proposal it commits to | What exactly did the investigator claim, and on what evidence? |
| **validation** · **evaluation** | independent verdicts, scoring, baselines, our answer keys | Who owns the answer key and when is it consulted? |
| **telemetry** | traces, run artifacts, reporting, cost/latency, CI | If a behaviour is not in the trace, what can you prove? |
| **integration** | the end-to-end path through all of the above | Does one command still take an incident to a report? |

Capabilities describe the software, never a division of the team. Every boundary above
has two sides, so no change stays inside one capability for long, and no capability
belongs to one person.

## Before you build

Read [inherited/](inherited/). Three short documents carrying what a previous
implementation of this system cost to learn:

- **CONFORMANCE.md** — fifteen audited defects, restated as requirements for your code
- **AUTHORITY_LIFECYCLE.md** — boundary 4, and the mistake that produced it
- **CONTROLS.md** — how we know investigating beats guessing, and why a perfect score is a
  problem

Their tests are your requirements. Their implementation is not your implementation. And
their **results are not our results** — a number measured on that system says nothing
about this one until this one has produced its own.

## The world the incidents come from

The architecture above is domain-independent. The operational world it runs against is not
a detail — it decides whether ADII reads as an incident investigator or as an SQL agent, so
its design is a shared decision upstream of any implementation work:
[DATA_WORLD_v0.md](DATA_WORLD_v0.md).

## Start here

```bash
python -m adii.examples.walkthrough --step
```

## Your first contribution

Nobody is assigned a subsystem, so nobody has to wait for permission to touch one. The
path in is the same for everyone:

1. **Run it.** `python -m adii.demo`, then the walkthrough above. Both work with nothing
   installed beyond `requirements.txt` and no API key.
2. **Read the vocabulary.** `02_src/adii/contracts/core.py` — eight types, and the only
   thing every part of the system agrees on.
3. **Read one package README.** Pick the capability the task you want touches. They are
   short and they say what the component is for.
4. **Take a task from the shared backlog**, or write one with
   [task_template.md](task_template.md). Name the capability it touches; a task that
   touches three is normal.
5. **Open a PR.** [review_playbook.md](review_playbook.md) is the merge gate. The short
   version: you have to be able to explain what you merged.

If you cannot find a task, the most useful first contribution is usually a test for
something that is currently only true by convention. `02_src/tests/architecture/` is what
that looks like when it works.
