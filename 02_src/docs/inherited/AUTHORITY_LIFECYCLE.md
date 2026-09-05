# Authorities have a lifecycle

A real mistake and the boundary it produced. The fix is structural rather than
"be more careful", and it is not obvious in advance.

## What happened

ADII's evaluation authority is an **answer key**: one frozen file per incident, pinned by
SHA-256, saying what the correct disposition was. Freeze it, score against it, and the
result means something. Edit it afterwards and the result means nothing.

The next piece of work needed a second thing: for each incident, *which observations a
correct decision must have actually cited*. Call it **decisive evidence**. The design put
it in the answer key — one authority, one file. Sensible.

Then two answer keys were authored and frozen, before the decisive-evidence field existed.

That is the whole mistake, and it is fatal in a specific way. The keys were frozen. Adding
a field would change their hash. Changing their hash would invalidate the evidence already
scored against them. **There was nowhere left to put decisive evidence.** Not "it would be
awkward" — genuinely nowhere.

## Why it was not a carelessness problem

The two authorities **freeze at different times**:

```text
answer key        frozen the moment a scenario is first scored
decisive evidence authored later, once you know what grounding needs to measure
```

Anything merged into one artifact must freeze at the *earliest* of its parts' freeze times.
So merging them was wrong the moment it was designed, whether or not anyone slipped. No
amount of care fixes it — only a different structure does.

## The fix

Two artifacts, hash-bound:

```text
answer key    v2   disposition · root cause · repair · escalation reason
grounding key v1   decisive tool/argument predicates
                   ├─ names the answer key it belongs to
                   └─ carries that key's SHA-256
```

The grounding key is authored later and frozen separately. It is bound to **exactly one
version of exactly one answer key**, so two authorities that disagree about a scenario
cannot be paired by accident. Loading refuses six ways: unfrozen, changed since freezing,
wrong filename, digest moved, bound to the wrong schema version, or disagreeing about which
scenario it describes. None of those is a warning.

## The boundary, stated generally

> **An authority frozen before it is complete cannot be completed.**
> Authorities that freeze at different times must be different artifacts, bound to each
> other by hash rather than merged.

`02_src/docs/architecture.md` carries three other boundaries — agent vs tools, agent vs validator,
contestant vs judge. This is the only one about *time* rather than about who may know
what.

## What to do with it

When you are about to freeze anything — an answer key, a scoring rule, a prompt, a
configuration — ask two questions:

1. **Is this complete?** Not "is it good enough", but: is there a part of it I know I will
   need to author later?
2. **Does everything in this artifact freeze at the same time?** If not, split it now,
   while splitting is still free.

The cost of asking is a minute. The cost of not asking is an authority you cannot finish
and cannot reopen.
