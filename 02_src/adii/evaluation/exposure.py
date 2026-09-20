"""Offline exposure inventory; no reserve selection and no inferred non-exposure.

Candidate identities are the source campaign's custom_id, never proposal hashes.
Only candidate-linked exposure evidence changes UNKNOWN_EXPOSURE. This collector
has no positive non-exposure authority, so it cannot emit KNOWN_UNEXPOSED.
Private inputs and output belong outside the team checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

STATES = ("KNOWN_EXPOSED", "KNOWN_UNEXPOSED", "UNKNOWN_EXPOSURE")


def encoded(value: object) -> str:
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"


def inventory(corpus: bytes, evidence: list[dict], sources: list[dict]) -> dict:
    """Evidence rows name exact custom_ids and source hash/field provenance.

    This is a bounded evidence inventory, not a certification of blind eligibility.
    Generation by a source model is not subsequent investigative/research exposure.
    """
    candidates = {}
    for line in corpus.splitlines():
        row = json.loads(line)
        identity = row["custom_id"]
        if not isinstance(identity, str) or not identity.strip() or identity in candidates:
            raise ValueError("custom_id must be a unique nonempty string")
        candidates[identity] = []
    for item in evidence:
        if item["custom_id"] not in candidates:
            raise ValueError("exposure identity is outside the candidate universe")
        candidates[item["custom_id"]].append(item["provenance"])
    rows = []
    for identity, refs in sorted(candidates.items()):
        refs = sorted({encoded(ref): ref for ref in refs}.values(), key=encoded)
        rows.append({"custom_id": identity,
                     "classification": "KNOWN_EXPOSED" if refs else "UNKNOWN_EXPOSURE",
                     "evidence": refs})
    return {"format": "adii.exposure_inventory/v1", "identity_field": "custom_id",
            "corpus_sha256": hashlib.sha256(corpus).hexdigest(),
            "counts": {state: sum(r["classification"] == state for r in rows)
                       for state in STATES},
            "scope": "Recorded candidate-linked exposure only; no non-exposure certification",
            "sources": sorted(sources, key=encoded), "candidates": rows}


def collect(corpus: bytes, research_root: Path, model_receipts: tuple[Path, ...] = ()) -> dict:
    """Read the existing exploratory selections and fixture provenance, not proposal text.

    Optional model receipts must explicitly link custom_id, model and timestamp.
    The historical first_model_exposure.json has no such link: retain it as context.
    The semantic-geometry sample is context only, never a reserve or non-exposure proof.
    """
    sources, evidence = [], []
    corpus_hash = hashlib.sha256(corpus).hexdigest()

    def read(path: Path, name: str, use: str) -> tuple[object, dict]:
        raw = path.read_bytes()
        ref = {"source": name, "sha256": hashlib.sha256(raw).hexdigest(), "use": use}
        sources.append(ref)
        return json.loads(raw) if path.suffix == ".json" else raw.decode("utf-8"), ref

    def add(ids: list[str], ref: dict, field: str) -> None:
        for identity in ids:
            evidence.append({"custom_id": identity,
                             "provenance": {**ref, "field": field}})

    for version in ("v1", "v2"):
        name = f"exploratory_capabilities_{version}/selection.json"
        doc, ref = read(research_root / name, name, "unblinded_research")
        if (doc["source_corpus_sha256"] != corpus_hash
                or not doc["evidence_class"].startswith("UNBLINDED_AI_ASSISTED")):
            raise ValueError("selection must bind this corpus and declare unblinded analysis")
        add(doc["selected_ids"], ref, "/selected_ids")
    name = "quota_cache_fixture_v1/receipt_v2.json"
    doc, ref = read(research_root / name, name, "engineering_use")
    if doc["source"]["corpus_sha256"] != corpus_hash:
        raise ValueError("fixture receipt binds a different corpus")
    add([doc["source"]["proposal_id"]], ref, "/source/proposal_id")
    for name in ("semantic_geometry_v1/SAMPLE_FREEZE.md",
                 "semantic_geometry_v1/custodian_sample_v1/selected_ids.json"):
        read(research_root / name, name, "sample_only_not_exposure_or_non_exposure")
    read(research_root.parent / "first_model_exposure.json", "../first_model_exposure.json",
         "earlier_incidents_no_discovery_candidate_mapping")
    for path in model_receipts:
        doc, ref = read(path, path.name, "recorded_model_exposure")
        if doc.get("corpus_sha256") != corpus_hash or not all(
                isinstance(doc.get(k), str) and doc[k].strip()
                   for k in ("custom_id", "model", "timestamp")):
            raise ValueError("model receipt needs corpus binding and explicit "
                             "custom_id, model and timestamp")
        add([doc["custom_id"]], ref, "/custom_id")
    return inventory(corpus, evidence, sources)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--research-root", type=Path, required=True)
    parser.add_argument("--model-exposure", type=Path, action="append", default=[])
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    corpus = args.corpus.read_bytes()
    if hashlib.sha256(corpus).hexdigest() != args.expected_sha256:
        raise ValueError("corpus digest mismatch")
    result = collect(corpus, args.research_root, tuple(args.model_exposure))
    if len(result["candidates"]) != args.expected_count:
        raise ValueError("corpus candidate count mismatch")
    with args.out.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(encoded(result))
    print(encoded(result["counts"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
