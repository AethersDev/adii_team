"""D-15 / D8: C's contribution to D's receipt — the artefact digests.

CONFORMANCE.md D8 — "the receipt naming what is about to be spent — the
artefact, the configuration, the source revisions, the reason it is
permitted — is written and flushed before the irreversible call." D8's
own "Depends on" line names this exactly: "C's freeze identifiers."

C owns exactly one of D8's four receipt fields: THE ARTEFACT — proof of
which exact answer key (and, when one exists, which grounding key) a run
was scored against, so a receipt written before an irreversible model
call can truthfully say which frozen authority governs it. Configuration,
source revisions, and the permission reason are D's own fields, built
from D's own state — this module does not attempt them.

This is a thin, deliberate wrapper over freeze.py's own digest
computation (C2) and grounding.py's pairing (C3) — it introduces no new
way of computing a digest. D calls get_receipt_artefact() (or
get_receipt_artefact_with_grounding()) by filename, already knowing which
answer key a run is about to use, and gets back exactly the entries D8
says a receipt must name.
"""
from __future__ import annotations

from pathlib import Path

from .freeze import digest_path_for, load_frozen_answer_key
from .grounding import load_grounding_key


def get_receipt_artefact(answer_key_path: Path) -> dict:
    """Return one receipt-ready entry naming a frozen answer key.

    Returns {"kind": "answer_key", "path": str, "digest": str}. `path` is
    the filename only (not an absolute path — a receipt should name what
    the artefact is, not where it happens to sit on one machine), matching
    grounding.py's own "answer_key_filename" convention (C3) so the two
    modules agree on how an answer key is named across this directory.

    Raises the same errors freeze.load_frozen_answer_key already raises:
    FileNotFoundError if the key was never frozen, ValueError if its
    bytes have changed since freezing. A receipt must never be built from
    an artefact that fails either check — D8 exists precisely so nothing
    irreversible happens on the strength of an artefact that turned out
    to be unpinned or altered.
    """
    answer_key_path = Path(answer_key_path)
    # raises if unfrozen or mutated; digest below is then trustworthy
    load_frozen_answer_key(answer_key_path)
    digest = digest_path_for(answer_key_path).read_text(encoding="utf-8").strip()

    return {"kind": "answer_key", "path": answer_key_path.name, "digest": digest}


def get_receipt_artefact_with_grounding(
    answer_key_path: Path, grounding_key_path: Path
) -> list[dict]:
    """Return receipt-ready entries for a bound answer-key/grounding-key pair.

    Returns a list of two entries: the answer key's own (from
    get_receipt_artefact) and the grounding key's ({"kind":
    "grounding_key", "path": ..., "digest": ...} — the grounding key's own
    file digest, distinct from the answer_key_digest it carries inside
    itself for C3's pairing check).

    Raises whatever grounding.load_grounding_key raises if the pairing
    itself is broken (unfrozen answer key, changed since authoring, wrong
    scenario) — a receipt is refused the same way a scoring run would be,
    for the same reason: an artefact pairing that does not verify is not
    something a receipt can truthfully vouch for.
    """
    from .freeze import compute_digest

    answer_key_path = Path(answer_key_path)
    grounding_key_path = Path(grounding_key_path)

    # raises if the pairing is broken
    load_grounding_key(grounding_key_path, answer_key_dir=answer_key_path.parent)

    answer_key_entry = get_receipt_artefact(answer_key_path)
    grounding_key_entry = {
        "kind": "grounding_key",
        "path": grounding_key_path.name,
        "digest": compute_digest(grounding_key_path),
    }
    return [answer_key_entry, grounding_key_entry]
