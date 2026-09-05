# Task template

Fill this in **before** starting a piece of work — your own, or a coding agent's. It
takes five minutes and it is the same five questions the PR will ask you at the end, so
answering them first is not overhead; it is the work.

Copy the block below into the issue or the branch description.

```markdown
## Task

<!-- One sentence. What is true after this is done that is not true now? -->

## Why it matters

<!-- Which milestone does this move, and what is blocked until it lands? -->

## Affected system capability

<!-- One or more. A task that touches several is normal and worth saying out loud. -->

agent-loop / tools / state / evidence / decision / validation / evaluation / telemetry /
integration

- Capabilities:
- Files likely involved:
- Boundaries this crosses: <!-- see 02_src/docs/architecture.md -->

## Inputs and outputs

- Inputs:
- Outputs:
- Contract types involved: <!-- from 02_src/adii/contracts/core.py -->

## Acceptance test

<!-- How anyone else can tell this is done, by running something. -->

- Unit:
- Contract:
- Integration:
<!-- If the answer is "manually", stop and find the test. -->

## Dependencies and blockers

<!-- What has to exist first, and who is building it. -->

## Failure modes

<!-- Two or three. What does this do when its input is wrong, missing, or hostile? -->

## Agent involvement

- What a coding agent will generate:
- What I will inspect line by line before it merges:

## Reviewer

<!-- Someone who did not write it. Not a permanent authority for this area -- there
     is no such thing here. Prefer whoever has least context, so it spreads. -->
```

## Why these fields

**Affected system capability** because the architecture tests fail the build on a
boundary crossing, and finding that out at PR time wastes a day.
`02_src/tests/architecture/` is the list. Naming a capability is not claiming it: nobody
owns one, and a task that names three is a task worth reviewing carefully, not a mistake.

**Contract types** because `02_src/adii/contracts/core.py` is the vocabulary four people
and many agent sessions share. Work that invents a parallel shape has to be redone.

**Acceptance test** before the code exists, because a test written afterwards tends to
describe what the code happens to do.

**Reviewer** named up front, because cross-review is how knowledge stops living in one
head. Prefer the person with least context in that part of the runtime, not the most.

**Agent involvement** because the merge gate is not "does it work" but *"can its human
author explain it"*. A perfect generated implementation nobody can debug is not done.
See [review_playbook.md](review_playbook.md) for the five questions asked at the end.
