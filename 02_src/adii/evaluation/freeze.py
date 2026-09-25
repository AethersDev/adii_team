"""C2: answer keys are frozen by hash and never edited.

requirement C2 — "each key is pinned by digest and loaded through a
function that refuses on mismatch. A correction is a new file, never an
in-place edit."

The digest lives in a companion file, `<answer_key>.sha256`, next to the
answer key it pins — never inside the answer key itself. Hashing a JSON
file that contains its own hash means excluding that one field from the
hash computation, which is a second, unenforced contract about which byte
ranges count. A separate file has no such problem: the whole answer key
file is hashed, byte for byte, with nothing carved out.

Freezing is a distinct, explicit action (freeze_answer_key), not something
that happens implicitly on first score. An answer key with no `.sha256`
file next to it has never been frozen and is not eligible for scoring
against — see load_frozen_answer_key.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

DIGEST_SUFFIX = ".sha256"


def compute_digest(path: Path) -> str:
    """Return the hex SHA-256 digest of a file's exact bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest_path_for(answer_key_path: Path) -> Path:
    return answer_key_path.with_name(answer_key_path.name + DIGEST_SUFFIX)


def freeze_answer_key(answer_key_path: Path) -> str:
    """Pin an answer key's current bytes by writing its digest file.

    Raises FileExistsError if a digest file already exists — freezing is a
    one-time action per file. Re-freezing the same filename after an edit
    would silently move the pin, which is exactly what C2 forbids: "a
    correction is a new file, never an in-place edit." To fix a frozen key,
    author a new file under a new name and freeze that instead.

    Returns the digest that was written.
    """
    answer_key_path = Path(answer_key_path)
    digest_path = digest_path_for(answer_key_path)
    if digest_path.exists():
        raise FileExistsError(
            f"{digest_path} already exists — {answer_key_path.name} is already frozen. "
            f"A correction must be a new file, never a re-freeze of this one."
        )
    digest = compute_digest(answer_key_path)
    digest_path.write_text(digest + "\n", encoding="utf-8", newline="\n")
    return digest


def load_frozen_answer_key(answer_key_path: Path) -> dict:
    """Load an answer key only if its current bytes match its frozen digest.

    Raises FileNotFoundError if the key has never been frozen (no .sha256
    file exists next to it) — an unfrozen key is not eligible for scoring
    against, per C2.

    Raises ValueError if the current file's digest does not match what was
    frozen — the file changed after freezing, which is exactly the
    situation C2 exists to make impossible to score against silently.
    """
    answer_key_path = Path(answer_key_path)
    digest_path = digest_path_for(answer_key_path)

    if not digest_path.exists():
        raise FileNotFoundError(
            f"{answer_key_path.name} has never been frozen — no {digest_path.name} found. "
            f"Call freeze_answer_key() first, deliberately, before scoring against it."
        )

    frozen_digest = digest_path.read_text(encoding="utf-8").strip()
    current_digest = compute_digest(answer_key_path)

    if current_digest != frozen_digest:
        raise ValueError(
            f"{answer_key_path.name} has changed since it was frozen: "
            f"expected digest {frozen_digest}, got {current_digest}. "
            f"An answer key must never be edited after freezing — author a new file instead."
        )

    return json.loads(answer_key_path.read_text(encoding="utf-8"))
