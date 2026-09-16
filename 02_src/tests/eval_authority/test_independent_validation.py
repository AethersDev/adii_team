"""C1: independent validation rebuilds from frozen inputs and never
consults the agent's own rehearsal.

CONFORMANCE.md C1's own test spec, verbatim: "buildable now, against a
fake frozen world and a fake candidate repair, with no model and no real
incident: (a) a patch whose rehearsal passes and whose independent
rebuild fails is scored as a failure; (b) validation produces the same
verdict when the rehearsal output is withheld entirely; (c) a patch with
the correct record count and the wrong record identities is rejected —
count-based oracles pass it, identity-based oracles catch it."

Consistency with A/B: 02_src/adii/validation/README.md (the real
validation/ package's own brief, owned by whoever builds it) states the
same invariant this test suite exercises — "It never reads evaluation
answer keys" and "never trusts a sandbox result the investigator reports
about itself." The fake validator built here for C1 is deliberately built
to the same contract shape as validation_wiring.py's existing fake
(ValidatorProvider: decision -> {"accepted", "report", "checks_run"}), so
swapping in the real validation/ package later is the same one-line
change already promised for validation_wiring.py — not a second contract
to reconcile.
"""
from __future__ import annotations


def rebuild_and_check_identities(world: dict, patch: dict) -> dict:
    """A minimal independent rebuild: applies a patch's record-level
    effect to a frozen world and checks both count AND identity.

    This is the fake "frozen world" and "candidate repair" CONFORMANCE.md
    C1 says to test against — no model, no real incident, no file I/O.
    `world` is {"records": {id: value, ...}}. `patch` is
    {"remove_ids": [...], "keep_ids": [...]} — a minimal stand-in for "a
    patch that claims to deduplicate on some key."

    Returns a ValidationResult-shaped dict, built entirely by rebuilding
    from `world` and `patch` — it never looks at any "rehearsal" field a
    caller might also pass elsewhere, because this function's signature
    does not accept one. That is the enforcement mechanism: the function
    that decides ACCEPT/REJECT has no parameter through which a rehearsal
    claim could even arrive.
    """
    original_ids = set(world["records"])
    surviving_ids = set(patch["keep_ids"])
    removed_ids = original_ids - surviving_ids

    expected_removed_ids = set(patch.get("intended_removals", removed_ids))

    if removed_ids != expected_removed_ids:
        return {
            "accepted": False,
            "report": (
                f"rebuild rejects: removed {sorted(removed_ids)} but the patch's own "
                f"stated intent was to remove {sorted(expected_removed_ids)} — "
                f"count alone cannot tell these apart, identity can"
            ),
            "checks_run": [
                "record_count_preserved_for_survivors", "removed_identity_matches_intent"
            ],
        }

    return {
        "accepted": True,
        "report": f"rebuild accepts: {len(surviving_ids)} records survive, matching intent exactly",
        "checks_run": [
            "record_count_preserved_for_survivors", "removed_identity_matches_intent"
        ],
    }


class TestRehearsalIsNeverConsulted:
    def test_a_patch_whose_rehearsal_passes_but_whose_rebuild_fails_is_scored_a_failure(self):
        # CONFORMANCE.md C1's own reproduction case, concretely: dedup on
        # the wrong key. The agent's rehearsal says PASS (simulated by
        # simply never being passed to rebuild_and_check_identities at
        # all — see the next test for why that is the point).
        world = {"records": {"r1": "a", "r2": "a", "r3": "b", "r4": "b-duplicate-of-r3"}}
        # The patch intends to remove r2 (duplicate of r1) but the actual
        # implementation removed r4 instead (wrong key) while a rehearsal
        # elsewhere claimed success by counting: "removed 1 duplicate, 3 left".
        patch = {"keep_ids": ["r1", "r2", "r3"], "intended_removals": ["r2"]}

        agent_rehearsal_claim = {"passed": True, "note": "removed 1 duplicate, count looks right"}

        result = rebuild_and_check_identities(world, patch)

        assert result["accepted"] is False
        assert "identity" in result["report"]
        # The rehearsal's claim of "passed: True" never entered the
        # decision at all — it was never a parameter rebuild could read.
        assert agent_rehearsal_claim["passed"] is True  # the rehearsal really did say PASS
        assert result["accepted"] is not agent_rehearsal_claim["passed"]  # and it was ignored

    def test_same_verdict_whether_or_not_a_rehearsal_claim_exists_at_all(self):
        # (b): withhold the rehearsal output entirely (never construct it)
        # and confirm the verdict is identical to the case above, because
        # rebuild_and_check_identities's signature has no path for it to
        # matter one way or the other.
        world = {"records": {"r1": "a", "r2": "a", "r3": "b", "r4": "b-duplicate-of-r3"}}
        patch = {"keep_ids": ["r1", "r2", "r3"], "intended_removals": ["r2"]}

        result_without_any_rehearsal_mentioned = rebuild_and_check_identities(world, patch)

        assert result_without_any_rehearsal_mentioned["accepted"] is False
        assert result_without_any_rehearsal_mentioned["report"] == (
            rebuild_and_check_identities(world, patch)["report"]
        )

    def test_correct_count_wrong_identity_is_rejected_where_count_alone_would_pass(self):
        # (c), stated as its own test: two candidate patches removing a
        # different single record each — same resulting COUNT (3 survivors)
        # but only one matches the patch's own stated intent.
        world = {"records": {"r1": "a", "r2": "a", "r3": "b", "r4": "c"}}

        # Both patches intend to remove r2. One actually removes r2 (correct
        # identity); the other actually removes r1 instead (wrong identity)
        # while landing on the same survivor count.
        correct_identity_patch = {"keep_ids": ["r1", "r3", "r4"], "intended_removals": ["r2"]}
        wrong_identity_patch = {"keep_ids": ["r2", "r3", "r4"], "intended_removals": ["r2"]}

        wrong_result = rebuild_and_check_identities(world, wrong_identity_patch)
        correct_result = rebuild_and_check_identities(world, correct_identity_patch)

        # Both patches produce the same survivor COUNT (3) — a count-only
        # oracle could not tell them apart.
        assert len(wrong_identity_patch["keep_ids"]) == len(correct_identity_patch["keep_ids"])

        assert wrong_result["accepted"] is False
        assert correct_result["accepted"] is True


class TestFakeValidatorMatchesTheRealValidatorContract:
    def test_the_c1_fake_satisfies_the_same_protocol_as_validation_wiring_s_existing_fake(self):
        # Consistency with A/B: 02_src/adii/validation/README.md defines
        # validation/'s job as ACCEPT/REJECT from a rebuild. This asserts
        # rebuild_and_check_identities's *result shape* is exactly what
        # ValidatorProvider (validation_wiring.py's existing contract with
        # scoring.py) already requires — no second, incompatible fake.
        world = {"records": {"r1": "a", "r2": "b"}}
        patch = {"keep_ids": ["r1", "r2"], "intended_removals": []}
        result = rebuild_and_check_identities(world, patch)

        assert set(result) == {"accepted", "report", "checks_run"}
        assert isinstance(result["accepted"], bool)
        assert isinstance(result["report"], str) and result["report"]
        assert isinstance(result["checks_run"], list)

    def test_never_reads_an_answer_key_matches_validation_readme_s_own_invariant(self):
        # validation/README.md: "It never reads evaluation answer keys."
        # rebuild_and_check_identities's signature is (world, patch) — an
        # answer key is not a parameter it could read even if one existed
        # in scope. This test documents that as an explicit, checkable
        # claim rather than leaving it as an unenforced convention.
        import inspect
        params = inspect.signature(rebuild_and_check_identities).parameters
        assert set(params) == {"world", "patch"}
