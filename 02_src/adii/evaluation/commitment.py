"""The reserve commitment — plan D-20: the partition is frozen before anything crosses.

    python -m adii.evaluation.commitment --partition PRIVATE/partition.json \\
        --campaign NAME --custodian NAME --out 02_src/adii/evaluation/reserve_commitment.json
    python -m adii.evaluation.commitment --verify PRIVATE/partition.json \\
        --commitment 02_src/adii/evaluation/reserve_commitment.json

The private partition maps every candidate in the discovery corpus to exactly one of two
classes — `reserve` or `development_candidate` — and never enters the repository. What
enters is its digest over a canonical form, with counts and provenance: enough for the
custodian to later prove any one candidate's pre-existing assignment (by producing the
partition and re-deriving the digest), and not enough for anyone to reconstruct the
reserve. A digest of the reserve *list* alone would not do: it cannot show that a
declassified candidate was outside the reserve without disclosing the list.

The commitment is written before the first development incident is compiled, and git
history is what proves the order. Every declassified incident's provenance then cites
this digest — a test holds that seam once the first incident lands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

SCHEMA = "adii.reserve_commitment/v1"
NAME = "reserve_commitment.json"
CLASSES = ("reserve", "development_candidate")
CANONICALIZATION = "json: object of candidate id -> class, keys sorted, separators ',' and ':', " \
                   "non-ASCII preserved, utf-8, one trailing newline"
FIELDS = ("schema", "source_campaign", "partition_digest", "canonicalization",
          "reserved_count", "development_candidate_count", "created_at", "custodian")


def canonical(partition: dict[str, str]) -> bytes:
    """One byte string per partition, whatever order or whitespace it was written in."""
    for candidate, assigned in partition.items():
        if not isinstance(candidate, str) or not candidate:
            raise ValueError("every candidate id is a non-empty string")
        if assigned not in CLASSES:
            raise ValueError(f"{candidate!r} is assigned {assigned!r}; a partition assigns "
                             f"exactly one of {CLASSES}")
    text = json.dumps(dict(sorted(partition.items())), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return (text + "\n").encode("utf-8")


def digest_of(partition: dict[str, str]) -> str:
    return "sha256:" + hashlib.sha256(canonical(partition)).hexdigest()


def commit(partition: dict[str, str], *, campaign: str, custodian: str,
           created_at: str | None = None) -> dict:
    """The team-visible document: the digest and the counts, never the assignments."""
    if not campaign.strip() or not custodian.strip():
        raise ValueError("a commitment names its campaign and its custodian")
    digest = digest_of(partition)                       # validates every assignment first
    return {
        "schema": SCHEMA, "source_campaign": campaign, "partition_digest": digest,
        "canonicalization": CANONICALIZATION,
        "reserved_count": sum(1 for v in partition.values() if v == "reserve"),
        "development_candidate_count": sum(1 for v in partition.values()
                                           if v == "development_candidate"),
        "created_at": created_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "custodian": custodian,
    }


def read_commitment(path: Path) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != SCHEMA:
        raise ValueError(f"unknown commitment schema {document.get('schema')!r}")
    missing = [f for f in FIELDS if f not in document]
    if missing:
        raise ValueError(f"commitment is missing {missing}")
    return document


def verify(partition: dict[str, str], commitment: dict) -> bool:
    """True when this partition is the one the commitment was made over: same digest, same
    counts, same canonical form."""
    return (commitment["partition_digest"] == digest_of(partition)
            and commitment["canonicalization"] == CANONICALIZATION
            and commitment["reserved_count"] == sum(1 for v in partition.values() if v == "reserve")
            and commitment["development_candidate_count"]
            == sum(1 for v in partition.values() if v == "development_candidate"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m adii.evaluation.commitment",
                                     description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--partition", metavar="PATH", help="the private partition to commit")
    mode.add_argument("--verify", metavar="PATH", help="the private partition to verify")
    parser.add_argument("--campaign", help="the discovery campaign the partition covers")
    parser.add_argument("--custodian", help="who made the partition")
    parser.add_argument("--out", metavar="PATH", help="where the commitment is written")
    parser.add_argument("--commitment", metavar="PATH", help="the commitment to verify against")
    args = parser.parse_args(argv)
    if args.partition:
        if not (args.campaign and args.custodian and args.out):
            print("--partition needs --campaign, --custodian and --out")
            return 2
        partition = json.loads(Path(args.partition).read_text(encoding="utf-8"))
        document = commit(partition, campaign=args.campaign, custodian=args.custodian)
        out = Path(args.out)
        if out.exists():
            print(f"{out} exists: a commitment is made once; a new partition is a new campaign")
            return 1
        out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8", newline="\n")
        print(f"committed {document['reserved_count']} reserved and "
              f"{document['development_candidate_count']} development candidates as "
              f"{document['partition_digest']} in {out}")
        return 0
    if not args.commitment:
        print("--verify needs --commitment")
        return 2
    partition = json.loads(Path(args.verify).read_text(encoding="utf-8"))
    ok = verify(partition, read_commitment(Path(args.commitment)))
    print("the partition matches its commitment" if ok
          else "MISMATCH: this is not the partition the commitment was made over")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
