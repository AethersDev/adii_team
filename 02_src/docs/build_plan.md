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
walkthrough fixture, the demo (a teaching page then; the run inspector since 13 September),
architecture tests.

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

## M1 — Basic agent loop — DONE

**Goal** A model message goes out, a reply comes back, and the loop terminates on purpose
rather than by running out of turns.

**Why it matters** Without a loop there is no agent. This is the smallest thing that is
recognisably ADII rather than a script.

**Build** a scripted provider first; the message list; the turn loop; a budget; an explicit
stopping condition; the loop's own trace events.

**Demo** One incident in, a terminal decision out, with a scripted provider and no tools.

**Done when**
- [x] a scripted provider produces a deterministic run
- [x] the loop stops on a stated condition, not on an exception
- [x] a turn budget exists and is enforced
- [x] every turn appears in the trace
- [x] tests cover the stopping condition and the budget

Ticked 14 September from what `02_src/tests/unit/test_investigator_loop.py` proves. The
loop is not yet driven by the runtime and no provider exists; those are M7's next box and
M8, not this milestone.

**Suggested first task** The scripted provider, with one canned reply. It is small, it unblocks
everything else, and it is the piece most likely to be got wrong quietly.

**Likely files** `02_src/adii/investigator/`, `02_src/tests/unit/`

---

## M2 — Controlled tool use — DONE

**Goal** The model can request a tool, receive a structured observation, and continue.

**Why it matters** Without tools ADII is a chatbot reasoning from its prompt. The tool
layer is also the only place a boundary can refuse.

**Build** the tool contract; a registry; an executor; structured observations; error and
denial handling.

**Demo** The agent requests one controlled tool and uses its result in the next step.

**Done when**
- [x] a valid call executes and returns a `ToolResult`
- [x] an unknown tool is rejected without reaching the environment
- [x] malformed arguments are rejected with a usable message
- [x] `DENIED` is a normal outcome, distinguishable from an error
- [x] each observation carries a stable evidence id
- [x] the trace records the request and the result

**Suggested first task** One simple deterministic demo tool.

**Likely files** `02_src/adii/tools/`, `02_src/adii/investigator/`, `02_src/tests/`

---

## M3 — Multi-step investigation — NEXT

**Goal** What the agent saw in step *n* changes what it asks for in step *n+1*.

**Why it matters** This is the difference between an investigator and a classifier.

**Build** investigation state; evidence accumulation; a next-action choice that reads that
state.

**Demo** A run where the second tool call is provably caused by the first observation.

**Done when**
- [x] state is a value, inspectable and serialisable
- [ ] a decision can cite the evidence ids it rests on
- [ ] a run with different observations takes a different path
- [ ] the trace shows why the loop continued

---

## M4 — Structured terminal decision

**Goal** The run ends in a machine-readable `InvestigationDecision`, not prose.

**Build** decision construction, disposition selection, evidence citation, schema
validation of the model's output.

**Done when**
- [x] the decision validates against the contract
- [ ] a malformed model answer is a scored failure, not a crash
- [ ] every claim cites an evidence id that exists
- [x] all three dispositions are reachable

---

## M5 — Candidate repair and escalation

**Goal** REPAIR carries a bounded candidate action; ESCALATE names what it needs and why it
stopped.

**Done when**
- [ ] a candidate action is expressed in the contract, not free text
- [ ] ESCALATE states the missing authority or evidence
- [ ] NO_REPAIR changes nothing and says why the world is legitimate

---

## M6 — Independent validation — DONE

**Goal** A separate authority accepts or rejects the candidate action.

**Why it matters** The investigator grading its own repair is the single failure this
architecture exists to prevent.

**Done when**
- [x] validation rebuilds from frozen inputs
- [x] it never reads the investigator's own claim about its sandbox
- [x] REJECT is reachable and tested
- [x] the reasons are machine-readable

Built as `validation/patching.py` (rebuilds a brand-new `ReadOnlyDatabase` from
patched SQL text — never mutates the investigator's own connection), `checks.py`
(three atomic checks, including the count-vs-identity check C1(c) requires), and
`validator.py` (`Validator.validate(context, decision) -> ValidationResult`,
satisfying `runtime.run.Validator` and driven end to end by
`run_incident` in `test_validation_end_to_end.py` — no fakes). `validate()`'s
signature has no parameter a rehearsal claim could arrive through
(`test_validator.py::TestNeverConsultsARehearsal`). An adapter,
`as_dict_validator`, satisfies `evaluation/validation_wiring.py`'s
`ValidatorProvider` shape for offline scoring
(`test_validation_wired_into_evaluation.py`).

**Wired 18 September**: `runtime/__main__.py`'s `--provider local` path now builds
`validation.validator.Validator()` instead of `runtime/live.py`'s `NoValidatorYet`
stand-in — a live REPAIR is rebuilt from frozen inputs and actually checked, proven
by `test_live_provider.py::test_a_live_repair_is_checked_by_the_real_validator`.
`NoValidatorYet` itself stays in `live.py`, unused on this path, until the D-1 trace
contract resolves what its remaining callers (if any) should do instead.

**Only incident covered**: `demo-learning-001` (the walkthrough world). An incident
`validate()` has no frozen world for raises `UnknownIncident`, recorded as an
`infrastructure_failure` rather than a fabricated verdict. Extending
`_WORLD_BUILDERS` in `validator.py` for additional incidents is required before
M7's real incidents can be validated, not before M6 itself is done — C1's test
spec is buildable and provable against one frozen world.

---

## M7 — End-to-end vertical slice

**Goal** One command takes an incident to an archived run and a readable report — with
the real investigator doing the investigating.

**From 16 September the tracks are integrated, and the objective test of the whole is
[green_line.md](green_line.md): twelve properties, each tied to the command or test that
demonstrates it, and the sequence to the first scored full-system run. How the result is
shown to an audience is [demo.md](demo.md): one incident, three layers, the machinery
revealed only once it answers a question the audience already has.**

**Demo** `python -m adii.runtime --incident demo-learning-001 --provider scripted && python -m adii.demo`

**Where it stands, 14 September.** The four boxes below are ticked by a slice in which the
investigator is a script replaying the walkthrough. That proved the runtime, the archive,
the report and the inspector. It did not prove the composition the milestone is named for:
A's loop exists and B's tools exist, but nothing invokes the loop from the runtime, and the
loop writes a trace of its own. So the milestone stays open, blocked on the trace event
contract (`plan_telemetry.md` D-1) and the adapter that wires A into the runtime.

**Complete when**, with no provider call, no judge and no development catalogue:
- [ ] A's loop is invoked by the real runtime, with the scripted provider
- [ ] it uses B's real tools, and their observation ids are carried, never re-minted
- [ ] one canonical trace is recorded at the boundaries — never A's trace and the runtime's merged afterwards
- [ ] every ending passes through the runtime boundary and lands as a termination class, a stop without a decision included
- [ ] the result is one `adii.run_record/v1` in the archive that the inspector renders

**Done when** — the original four, proven by the scripted slice on 13 September
- [x] one command, one incident, one run artifact
- [x] same commit green on Windows and macOS
- [x] the report shows evidence, decision, validation and cost
- [x] a scripted provider is still sufficient

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
