# Contributing

## The workflow

```bash
git switch -c your-name/short-description
# ... work ...
python -m ruff check 02_src
python -m pytest
git push -u origin your-name/short-description
# open a PR, watch CI, respond to review, merge, then:
git switch main && git pull
```

`main` is protected. Everything arrives through a PR with green CI on **Windows and
macOS**. "Works on my machine" is not an argument here; CI is the argument.

## The author-understanding gate

**No PR merges until its human author can answer these five questions in their own words.**

1. What problem does this change solve?
2. What are its inputs and outputs?
3. What important failure modes does it have?
4. How did you test it?
5. What did a coding agent generate that you had to inspect or correct?

Not line-by-line memorisation — operational understanding. A reviewer may ask for a
two-minute walkthrough on any significant change.

*Why this exists:* four people plus coding agents produce more code than four people can
review. Plausible, well-commented, well-tested code can still be wrong — an audit of the
reference implementation found fifteen real defects in exactly that kind of code, and
fixing them surfaced more; `02_src/docs/inherited/CONFORMANCE.md` carries the 39
requirements that resulted. This is what keeps generation speed from outrunning review.

## Who reviews what

**Review authority follows demonstrated depth in an area.** Once you have implemented a
component, debugged a real failure in it, and reviewed someone else's change against it,
you are the reviewer for that area. Until then, changes there take a second reviewer.

**The standing rule:**

| Change | Reviewer |
|---|---|
| internals of one component | anyone competent in that area |
| anything in `02_src/adii/contracts/` | **plus** a reviewer from every boundary it touches |
| scoring semantics (`evaluation/`) | **broad review** — it changes what "success" means |

Contracts are the one thing all four of us share, so a contract change is never a
one-person decision.

## Getting unstuck

**Stuck for about an hour? Say so.** Post four lines:

```text
WHAT I TRIED:
WHAT HAPPENED:
WHAT I EXPECTED:
ERROR/TEST:
```

The same format works for a teammate and for a coding agent.

## Daily update

Four lines:

```text
DONE:    get_schema works against DuckDB
NEXT:    read-only run_sql
BLOCKED: unsure how ToolError should serialise
PR:      #14
```

## The boundaries are tests, not requests

`02_src/tests/architecture/test_boundaries.py` fails the build when code crosses an architectural
boundary — the investigator reaching a database directly, something importing a private
repository, a contract growing a dependency. The failure message states the rule.

**Relaxing one of those tests is essentially never the fix.** If a boundary genuinely
needs to move, that is an architectural decision with cross-boundary review, not a test
edit. This exists because coding agents generate faster than four people can review, and
a rule that lives only in prose is a rule that gets violated in a PR where everything else
is green.

## Style

`ruff` settles formatting. Name things after what they mean in the architecture
(`ToolResult`, not `resp2`). Comments explain *why*; the code already says what.
