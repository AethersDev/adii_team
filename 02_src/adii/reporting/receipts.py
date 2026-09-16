"""The receipt: what is about to be spent, written and flushed before it is — inherited D8.

A run's label folder is reserved before the run; the receipt goes into it next, before the
investigator is invoked, and it stays whether the run ends in a decision, a bound, a
failure or a killed process. It names the artefacts the run is about to expose to a model
(by digest — the evaluation authority's frozen identifiers join these when they exist),
the configuration requested, the source revision, and the reason the spend is permitted.

Written *and flushed*: `flush()` then `fsync()`, so a process killed the instant after this
returns still leaves the receipt on disk. That is the whole point — there is no second
first exposure, and terminal scrollback is not a record.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from .record import source_revision

SCHEMA = "adii.receipt/v1"
NAME = "receipt.json"


def digest_of(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_receipt(folder: Path, *, label: str, artefacts: dict[str, str],
                  configuration: dict[str, object], reason: str) -> Path:
    """Write `folder/receipt.json` and flush it to disk before returning. `artefacts` maps a
    name to a digest; nothing here computes what the artefact means."""
    if not reason.strip():
        raise ValueError("a receipt names the reason the spend is permitted")
    document = {
        "schema": SCHEMA, "label": label,
        "written_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_revision": source_revision(),
        "artefacts": dict(artefacts), "configuration": dict(configuration), "reason": reason,
    }
    path = folder / NAME
    with path.open("w", encoding="utf-8", newline="\n") as sink:
        sink.write(json.dumps(document, indent=2, allow_nan=False) + "\n")
        sink.flush()
        os.fsync(sink.fileno())
    return path


def read_receipt(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != SCHEMA:
        raise ValueError(f"unknown receipt schema {document.get('schema')!r}")
    return document
