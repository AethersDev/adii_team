# Receipt artefacts — C's field in D's receipt (D-15 / D8)

**Who this is for:** whoever builds `reporting/receipts.py` (D8, unit D-15).

## What D8 needs, and which one piece is C's

CONFORMANCE.md D8: *"the receipt naming what is about to be spent — the
artefact, the configuration, the source revisions, the reason it is
permitted — is written and flushed before the irreversible call."*

Four fields. C owns exactly one: **the artefact** — proof of which frozen
answer key (and, when one exists, which grounding key) the run about to
happen is scored against. Configuration, source revisions, and the
permission reason are D's own, built from D's own state.

D8's own line: *"Depends on: C's freeze identifiers."* This file is those
identifiers, and how to get them.

## The one call you need

```python
from receipt_artefacts import get_receipt_artefact
from pathlib import Path

entry = get_receipt_artefact(Path("demo-learning-001.answer.json"))
# {"kind": "answer_key", "path": "demo-learning-001.answer.json",
#  "digest": "a7d195fa...e2f9e943"}
```

Put `entry` straight into the receipt's artefact list. That is the whole
integration — one function call, one dict, already the shape a strict-JSON
receipt can hold.

If the run's answer key also has a bound grounding key (C3), get both
entries in one call instead:

```python
from receipt_artefacts import get_receipt_artefact_with_grounding

entries = get_receipt_artefact_with_grounding(
    Path("demo-learning-001.answer.json"),
    Path("demo-learning-001.grounding.json"),
)
# [{"kind": "answer_key", "path": "...", "digest": "..."},
#  {"kind": "grounding_key", "path": "...", "digest": "..."}]
```

## What "this is the digest, this is the file it names" means here

| Field | What it is |
|---|---|
| `kind` | `"answer_key"` or `"grounding_key"` — which authority this entry names |
| `path` | the filename only (`demo-learning-001.answer.json`), never an absolute machine path — a receipt names *what*, not *where on this disk* |
| `digest` | the SHA-256 hex digest of that exact file's bytes, from its own `.sha256` pin (C2) |

The digest is not computed fresh from whatever bytes happen to be on disk
right now and trusted blindly — see the next section.

## Why this can fail, on purpose

Both functions raise instead of returning a partial or best-guess entry:

- **`FileNotFoundError`** — the answer key named has never been frozen
  (no `.sha256` beside it). A receipt cannot vouch for an artefact that
  was never pinned in the first place.
- **`ValueError`, "changed since it was frozen"** — the answer key's
  current bytes no longer match its `.sha256` pin. Something edited it
  after freezing. A receipt built from this would name a digest that no
  longer describes the file D is actually about to use.
- **`ValueError`, "changed since this grounding key was authored"** —
  (grounding call only) the grounding key's bound `answer_key_digest`
  disagrees with the answer key's current digest. Either the answer key
  moved after the grounding key was written, or the grounding key was
  never really paired with this answer key.

**None of these is a warning.** If a receipt cannot be built because one
of these raises, the irreversible call these functions gate must not
happen either — that is D8's whole point. Do not catch these exceptions
and substitute a placeholder digest; let the call that would have spent
money fail alongside the receipt.

## What this module deliberately does not do

- It does not build the receipt itself, decide the permission reason, or
  read D's configuration or source-revision state — those are D's fields.
- It does not compute a digest by any means other than `freeze.py`'s own
  (C2) — there is exactly one way an answer key's digest is computed
  anywhere in this directory, and this module calls it rather than
  re-implementing it.
- It does not cache a digest across calls — every call re-reads the
  current file and re-verifies it against its `.sha256` pin, so a receipt
  is always built from what is actually on disk at receipt time, not
  from a value computed earlier in a long-lived process.

## Tests

`test_receipt_artefacts.py` — 9 tests, covering: a normal frozen key, an
unfrozen key (refused), a key mutated after freezing (refused), the
`path` field's shape, JSON round-tripping, the grounding-pair case, and a
broken answer-key/grounding-key pairing (refused). Run with:

```bash
pytest test_receipt_artefacts.py -v
```
