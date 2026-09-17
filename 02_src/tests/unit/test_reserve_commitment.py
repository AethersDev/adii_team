"""Plan D-20: the partition is frozen before anything crosses. The commitment carries the
digest of the whole partition — every candidate's class — so the custodian can later prove
one candidate's pre-existing assignment, and nobody can reconstruct the reserve from it."""
from __future__ import annotations

import json

import pytest
from adii.evaluation.commitment import (
    CANONICALIZATION,
    SCHEMA,
    canonical,
    commit,
    digest_of,
    main,
    read_commitment,
    verify,
)

PARTITION = {"c-0001": "reserve", "c-0002": "development_candidate", "c-0003": "reserve",
             "c-0004": "development_candidate", "c-0005": "reserve"}


def test_the_canonical_form_ignores_order_and_whitespace_and_nothing_else():
    reordered = dict(reversed(list(PARTITION.items())))
    assert canonical(reordered) == canonical(PARTITION)
    assert digest_of(reordered) == digest_of(PARTITION)
    moved = {**PARTITION, "c-0002": "reserve"}          # one assignment changed
    assert digest_of(moved) != digest_of(PARTITION)
    with pytest.raises(ValueError, match="exactly one of"):
        digest_of({"c-0001": "blind"})
    with pytest.raises(ValueError, match="non-empty"):
        digest_of({"": "reserve"})


def test_the_commitment_carries_the_digest_and_the_counts_never_the_assignments():
    document = commit(PARTITION, campaign="batch40k-v2", custodian="the custodian",
                      created_at="2026-09-17T00:00:00+00:00")
    assert document["schema"] == SCHEMA
    assert document["partition_digest"] == digest_of(PARTITION)
    assert document["canonicalization"] == CANONICALIZATION
    assert (document["reserved_count"], document["development_candidate_count"]) == (3, 2)
    assert "c-0001" not in json.dumps(document)        # no candidate id leaves with it
    assert verify(PARTITION, document)
    assert not verify({**PARTITION, "c-0002": "reserve"}, document)
    with pytest.raises(ValueError, match="custodian"):
        commit(PARTITION, campaign="x", custodian=" ")


def test_the_command_writes_once_and_verifies_the_private_original(tmp_path, capsys):
    private = tmp_path / "partition.json"
    private.write_text(json.dumps(PARTITION), encoding="utf-8")
    out = tmp_path / "reserve_commitment.json"
    assert main(["--partition", str(private), "--campaign", "batch40k-v2",
                 "--custodian", "the custodian", "--out", str(out)]) == 0
    assert "3 reserved and 2 development" in capsys.readouterr().out
    document = read_commitment(out)
    assert document["source_campaign"] == "batch40k-v2" and document["created_at"]
    assert main(["--partition", str(private), "--campaign", "batch40k-v2",
                 "--custodian", "the custodian", "--out", str(out)]) == 1   # made once
    assert main(["--verify", str(private), "--commitment", str(out)]) == 0
    private.write_text(json.dumps({**PARTITION, "c-0005": "development_candidate"}),
                       encoding="utf-8")
    assert main(["--verify", str(private), "--commitment", str(out)]) == 1
    assert "MISMATCH" in capsys.readouterr().out
    out.write_text('{"schema": "adii.reserve_commitment/v9"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unknown commitment schema"):
        read_commitment(out)
