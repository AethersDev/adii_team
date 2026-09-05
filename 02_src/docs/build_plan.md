# Build plan

The canonical roadmap. Milestones, not people — a milestone is a piece of working system,
and anyone may pick up a task inside any of them.

Status marks here are the single source of truth for
[current_status.md](current_status.md), which is generated. Change a mark here; never edit
that file.

## Done when — the same four for every milestone

```text
CODE WORKS          the demo below runs
TESTS PASS          pytest and ruff green on Windows and macOS
DEMO WORKS          someone else can run it from the command in this file
ANOTHER TEAMMATE    a person who did not implement it can explain the flow
UNDERSTANDS IT      and run its demonstration
```

That last one is the explainability check, and it is not decoration. A milestone whose
only competent explainer is its author has produced code the team cannot maintain, debug,
or defend in a review — which is the failure mode this project is most exposed to.

---

## M0 — Everybody can run the repo — DONE

**Goal** A teammate on Windows or macOS clones, installs, tests and runs the walkthrough
without anyone touching their machine.

**Why it matters** Every later milestone is measured by "does it run for someone else". If
that is not true at M0 it is never true.

**Build** Cross-platform layout, pinned dependencies, environment check, contracts,
walkthrough fixture, vision demo, architecture tests.

**Demo** `pip install -r requirements.txt && pytest && python -m adii.demo`

**Done when**
- [x] clean clone installs from `requirements.txt` alone
- [x] `python 02_src/scripts/check_env.py` prints `Ready.`
- [x] tests and lint green
- [x] `python -m adii.demo` serves
- [x] `python -m adii.examples.walkthrough --step` runs
- [x] no API key required

**Likely files** the whole repository front door.

---

## M1 — Basic agent loop — NEXT

**Goal** A model message goes out, a reply comes back, and the loop terminates on purpose
rather than by running out of turns.

**Why it matters** Without a loop there is no agent. This is the smallest thing that is
recognisably ADII rather than a script.

**Build** a fake provider first; the message list; the turn loop; a budget; an explicit
stopping condition; the loop's own trace events.

**Demo** One incident in, a terminal decision out, with a fake provider and no tools.

**Done when**
- [ ] a fake provider produces a deterministic run
- [ ] the loop stops on a stated condition, not on an exception
- [ ] a turn budget exists and is enforced
- [ ] every turn appears in the trace
- [ ] tests cover the stopping condition and the budget

**Suggested first task** The fake provider, with one canned reply. It is small, it unblocks
everything else, and it is the piece most likely to be got wrong quietly.

**Likely files** `02_src/adii/investigator/`, `02_src/tests/unit/`

---

## M2 — Controlled tool use

**Goal** The model can request a tool, receive a structured observation, and continue.

**Why it matters** Without tools ADII is a chatbot reasoning from its prompt. The tool
layer is also the only place a boundary can refuse.

**Build** the tool contract; a registry; an executor; structured observations; error and
denial handling.

**Demo** The agent requests one controlled tool and uses its result in the next step.

**Done when**
- [ ] a valid call executes and returns a `ToolResult`
- [ ] an unknown tool is rejected without reaching the environment
- [ ] malformed arguments are rejected with a usable message
- [ ] `DENIED` is a normal outcome, distinguishable from an error
- [ ] each observation carries a stable evidence id
- [ ] the trace records the request and the result

**Suggested first task** One simple deterministic demo tool.

**Likely files** `02_src/adii/tools/`, `02_src/adii/investigator/`, `02_src/tests/`

---

## M3 — Multi-step investigation

**Goal** What the agent saw in step *n* changes what it asks for in step *n+1*.

**Why it matters** This is the difference between an investigator and a classifier.

**Build** investigation state; evidence accumulation; a next-action choice that reads that
state.

**Demo** A run where the second tool call is provably caused by the first observation.

**Done when**
- [ ] state is a value, inspectable and serialisable
- [ ] a decision can cite the evidence ids it rests on
- [ ] a run with different observations takes a different path
- [ ] the trace shows why the loop continued

---

## M4 — Structured terminal decision

**Goal** The run ends in a machine-readable `InvestigationDecision`, not prose.

**Build** decision construction, disposition selection, evidence citation, schema
validation of the model's output.

**Done when**
- [ ] the decision validates against the contract
- [ ] a malformed model answer is a scored failure, not a crash
- [ ] every claim cites an evidence id that exists
- [ ] all three dispositions are reachable

---

## M5 — Candidate repair and escalation

**Goal** REPAIR carries a bounded candidate action; ESCALATE names what it needs and why it
stopped.

**Done when**
- [ ] a candidate action is expressed in the contract, not free text
- [ ] ESCALATE states the missing authority or evidence
- [ ] NO_REPAIR changes nothing and says why the world is legitimate

---

## M6 — Independent validation

**Goal** A separate authority accepts or rejects the candidate action.

**Why it matters** The investigator grading its own repair is the single failure this
architecture exists to prevent.

**Done when**
- [ ] validation rebuilds from frozen inputs
- [ ] it never reads the investigator's own claim about its sandbox
- [ ] REJECT is reachable and tested
- [ ] the reasons are machine-readable

---

## M7 — End-to-end vertical slice

**Goal** One command takes an incident to an archived run and a readable report.

**Done when**
- [ ] one command, one incident, one run artifact
- [ ] same commit green on Windows and macOS
- [ ] the report shows evidence, decision, validation and cost
- [ ] a fake provider is still sufficient

---

## M8 — Reliability and failure handling

**Goal** The system behaves defensibly when the model, a tool, or the environment misbehaves.

**Done when**
- [ ] a model error is recorded as a model error, not a platform error
- [ ] a tool timeout is a `ToolResult`, not an exception escaping the loop
- [ ] budgets and stopping hold under bad input
- [ ] cost and latency are measured from the trace

---

## M9 — Freeze

**Goal** Investigator, configuration, metrics, validator and authority are frozen and
hashed before anything is measured.

**Done when**
- [ ] the model-facing surface is frozen and its hash recorded
- [ ] the scoring code is frozen
- [ ] no tuning happens after this point

---

## M10 — Unseen evaluation

**Goal** One blind run against material the system has not seen, scored by frozen code.

**Done when**
- [ ] the run is one-shot
- [ ] nothing is tuned after seeing outcomes
- [ ] the report shows success, failure, false repair, correct abstention, unnecessary
      escalation and repair rejection with equal honesty
