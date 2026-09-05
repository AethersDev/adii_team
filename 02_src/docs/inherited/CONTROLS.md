# How do we know investigating beats guessing?

The question the project exists to answer. It determines what "working" means, so it is
worth settling before building the thing it measures.

## The trap

Suppose you build ADII, point it at six incidents, and it gets all six right. Good system?

**You cannot tell.** Maybe investigation is what did it. Maybe the alert text alone was
enough and the tools were decoration. Maybe the incidents were easy. A score with nothing to
compare it against is not evidence, it is a number.

So you need **controls**: deliberately weaker systems run on the same incidents, so the
difference is attributable to the thing you added.

## The three arms

```text
always-escalate      deterministic. Answers ESCALATE every time. No model at all.
alert-only           the same model, same prompt, ZERO tools. Decides from the alert text.
full investigator    the same model, with the tool surface. What we are building.
```

The middle one is the interesting control. It isolates exactly one variable — **access to
evidence** — because everything else is held identical.

## What actually happened

Measured by the reference implementation on its own six frozen incidents, three repeats
each:

| Arm | Full success | False repair | Unsafe certainty | Unnecessary escalation |
|---|---:|---:|---:|---:|
| always-escalate | 2/6 | 0 | 0 | 4 |
| alert-only | 6/18 | 0 | 0 | 12 |
| full investigator | **18/18** | 0 | 0 | 0 |

Look closely at the alert-only row. **All eighteen of its answers were ESCALATE** — it is
decision-identical to the deterministic arm. It scored 6/18 only because two of the six
incidents genuinely warrant ESCALATE.

## Whose numbers these are

**Not ours.** That table was produced by a different codebase, on six incidents that are
not in this repository, under an evaluation protocol we did not write. It is prior art:
evidence that the comparison is worth running and that the middle arm is the informative
one.

The number to be careful with is 18/18. It is true, it is impressive, and quoting it as
what *this* system does would be a false claim that survives review because the figure is
real. Our results start empty and stay empty until our system produces them, against our
incidents, under a protocol we agreed before running it.

That cuts the other way too, and more usefully: the failure modes below were also measured
elsewhere, so treat them as *likely* rather than *established here*. If one of them does
not reproduce for us, that is a finding, not a discrepancy to explain away.

## The claim this supports — and the one it does not

Read the safety columns: alert-only had **zero** false repairs and **zero** unsafe
certainties. So safety is *not* the differentiator. Both arms were perfectly safe.

The honest claim is:

> The alert-only arm was maximally safe and maximally useless. Tool-mediated investigation
> preserved that safety while converting 12 of 18 blanket abstentions into correct action
> or correct non-action.

That is stronger than "our system is more accurate", because it survives the obvious
objection. *"Your baseline was weak"* does not land against a baseline that was the safest
policy available.

## Why 18/18 is a problem, not a victory

A perfect score has **no variance**, and a measurement with no variance cannot discriminate.
From that table you cannot distinguish:

- the investigator is excellent, from
- these six incidents are too easy

You also get no failure taxonomy — and you need observed failures to know what to improve
next. A benchmark everything passes has stopped measuring.

This is why the next incidents must be **adversarial**: ones that plausibly bait a false
repair, and ones that plausibly bait unsafe certainty. Not to make the system look worse —
to make the measurement mean something again.

## The instinct

When a system scores perfectly, ask what the score could not have told you — then build the
case that would have caught it.
