# Inherited knowledge

Three documents. None of them is code you should copy.

| File | What it is |
|---|---|
| [CONFORMANCE.md](CONFORMANCE.md) | Defects already found and paid for, restated as requirements your implementation must satisfy |
| [AUTHORITY_LIFECYCLE.md](AUTHORITY_LIFECYCLE.md) | A real freeze-ordering mistake and what it teaches about authorities |
| [CONTROLS.md](CONTROLS.md) | How we know investigating beats guessing — the comparison the project exists to make |

## Why these exist

A reference implementation of ADII reached a working investigator, ran a real evaluation,
and was then audited. The audit found **fifteen defects in code that already passed its own
tests** — several subtle, several detectable only during a paid run.

This repository is a fresh implementation, not a fork. **The reference implementation's
tests are our requirements; its code is not our code.** Read `CONFORMANCE.md` before
building the component it covers — each item is a test worth writing.

## The one-way rule

Knowledge crosses into this repository. Code and results do not.

```text
prior implementation ──▶ requirements, failure modes, invariants ──▶ this repository
prior implementation ──X──  code, answer keys, incidents, scores
```

The private repositories are not checked out on anyone's machine here, and nothing in
`02_src/adii/` may import them — `02_src/tests/architecture/` fails the build if something tries. This is
not secrecy for its own sake: a build that depends on a checkout only one person has is
broken for everyone else, and an evaluation authority held off-site is not an authority we
can defend.

The rule that is easiest to break by accident: **their measured results are not ours.**
`CONTROLS.md` carries a genuinely strong number. Reporting it as this system's performance
would be a false claim made entirely out of true figures.

If something here contradicts what you find in practice, practice wins — say so, and we
change the document. These are findings, not commandments.
