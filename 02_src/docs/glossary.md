# Glossary

Short on purpose. If a term needs a paragraph, it belongs in
[system_map.md](system_map.md) or [architecture.md](architecture.md).

**Incident**
The initial operational symptom ADII investigates. A number looks wrong.

**Observation**
A structured result returned by a controlled tool. Not a string the model wrote.

**Evidence id**
A stable identifier that lets a decision cite an observation that actually happened. A
claim without one is an assertion.

**Investigation state**
What the agent currently knows, suspects, has already tested, and still needs. The thing
that makes step *n+1* depend on step *n*.

**Disposition**
The one answer ADII commits to: REPAIR, NO_REPAIR or ESCALATE.

**REPAIR**
Evidence establishes a defect, and a justified bounded intervention exists.

**NO_REPAIR**
The observed change is legitimate. Intervention is not justified. Doing nothing is the
correct action, not a failure to act.

**ESCALATE**
ADII cannot safely or legitimately act — the evidence is not reachable, the authority is
not held, or no safe action exists. Escalating is a real answer, and escalating when the
question was answerable is a real error.

**Candidate action**
The bounded intervention the investigator proposes. Expressed in the contract, never as
prose.

**Validator**
Independent code that decides whether a candidate action is acceptable. It rebuilds from
frozen inputs and never asks the investigator about its own work.

**Validation**
*Can this proposed action be accepted?* Runs after the decision, inside the run.

**Evaluation**
*How did the investigator score against hidden truth?* Runs offline, outside the run, and
is never visible to the agent. Not a synonym for validation — different data, different
trust domain, different time.

**Answer key**
The hidden truth for an incident. Owned by the evaluation authority. If the investigator
can reach it, every number the project reports becomes meaningless.

**Trace**
The ordered record of what actually happened in a run. The source for every counter — if a
behaviour is not in the trace, nobody can prove it happened.

**Run record**
The persisted, public record of one investigation, `adii.run_record/v1`: context, trace,
how the run ended, decision, validation, counters, configuration, provenance. One strict
JSON document per run under `01_data/runs/<label>/record.json`; the inspector reads nothing
else. Also called the run artifact.

**Label**
The name a run is archived under. One path segment, reserved before the run starts, and
it names one run forever: a taken label is refused, never overwritten.

**Termination**
How a run ended: `submitted` with a decision, or without one — `bound_hit` and
`model_failure` are the loop's own words, carried unchanged; `infrastructure_failure` is a
defect of ours, named. A run leaves a record however it ended.

**Boundary**
A place where one component may only reach another through a defined contract, enforced by
a test rather than by agreement. There are three, and `architecture.md` names them.

**Capability**
A part of the system a task can name: agent-loop, tools, state, evidence, decision,
validation, evaluation, telemetry, integration. Capabilities describe software. Nobody owns
one.

**The operational world**
The synthetic environment incidents come from, specified in
[DATA_WORLD_v0.md](DATA_WORLD_v0.md). It is frozen at v0: extend it, do not revise it.
