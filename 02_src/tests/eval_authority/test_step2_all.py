"""Step 2 tests — wire in the validator.

"A REPAIR only counts if the fix itself is independently accepted, too."

Every STEP 2 test lives here: confirming a REPAIR never passes without a
validator, confirming the fake validator itself behaves correctly on the
three cases already on hand, and one end-to-end test wiring
validation_wiring together with the full score_decision — exactly as the
step promises: fake now, real later, with no change to any logic.
"""
import json
from pathlib import Path

import pytest

from adii.evaluation.judge import judge_repair
from adii.evaluation.scoring import score_decision
from adii.evaluation.validation_wiring import (
    fake_validator_accepts_everything_structurally_sound,
    get_validation_for,
)

HERE = Path(__file__).parent

if not (HERE / "demo-learning-001.answer.json").exists():
    pytest.skip(
        "blind answer keys not present — added post-freeze, kept out of the repo "
        "so the system under evaluation can never read them (see eval_authority "
        "OVERVIEW.md)",
        allow_module_level=True,
    )


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def key_001():
    return load("demo-learning-001.answer.json")


@pytest.fixture(scope="module")
def key_drill():
    return load("demo-learning-002-mismatch-drill.answer.json")


def fake_model_provider(prompt: str) -> str:
    if "amount_cents / 100" in prompt and "/ 100.0) * 100" not in prompt:
        return "correct — single conversion preserved, satisfies repair_must_satisfy."
    return "incorrect — the patch does not satisfy repair_must_satisfy."


def real_judge(decision, validation, answer_key):
    return judge_repair(decision, validation, answer_key, fake_model_provider)


# ---------------------------------------------------------------------------
# 2a. get_validation_for — a REPAIR always goes through the validator.
# ---------------------------------------------------------------------------

class TestValidatorIsAlwaysConsulted:
    def test_non_repair_dispositions_never_call_the_validator(self):
        def validator_that_must_not_run(decision):
            raise AssertionError("NO_REPAIR/ESCALATE have nothing to validate")

        decision = {"disposition": "NO_REPAIR"}
        assert get_validation_for(decision, validator_that_must_not_run) is None

    def test_repair_always_goes_through_the_validator(self, key_001):
        called = []

        def spy_validator(decision):
            called.append(decision)
            return {"accepted": True, "report": "ok", "checks_run": []}

        decision = {
            "disposition": "REPAIR",
            "patch": {"transforms/stg_orders.sql": "amount_cents / 100.0"},
        }
        get_validation_for(decision, spy_validator)
        assert called == [decision]


# ---------------------------------------------------------------------------
# 2b. The fake validator itself — honest about being a stand-in, but its
#     accept/reject behaviour must be provably correct on real fixtures.
# ---------------------------------------------------------------------------

class TestFakeValidator:
    def test_accepts_the_reference_style_single_conversion(self, key_001):
        decision = json.loads(json.dumps({
            "disposition": "REPAIR",
            "patch": {"transforms/stg_orders.sql": "amount_cents / 100.0 AS amount_usd"},
        }))
        result = fake_validator_accepts_everything_structurally_sound(decision)
        assert result["accepted"] is True

    def test_rejects_the_drill_s_real_error_patch(self, key_drill):
        case = key_drill["test_fixtures"]["case_real_error"]
        result = fake_validator_accepts_everything_structurally_sound(case["decision"])
        assert result["accepted"] is False

    def test_accepts_the_drill_s_plausible_alternative_patch(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        result = fake_validator_accepts_everything_structurally_sound(case["decision"])
        assert result["accepted"] is True


# ---------------------------------------------------------------------------
# 2c. Full wiring: score_decision fed by the validator, not a hand-written
#     ValidationResult — this is the actual promise of STEP 2.
# ---------------------------------------------------------------------------

class TestStep2Wiring:
    def test_exact_match_repair_is_validated_then_scored_correct(self, key_001):
        decision = {
            "disposition": "REPAIR",
            "root_cause_id": key_001["correct_root_cause_id"],
            "repair_id": key_001["repair_must_satisfy"]["reference_repair_id"],
            "patch": {"transforms/stg_orders.sql": "amount_cents / 100.0 AS amount_usd"},
        }
        validation = get_validation_for(decision, fake_validator_accepts_everything_structurally_sound)

        result = score_decision(decision, validation, key_001, judge=real_judge)
        assert result["verdict"] == "correct"
        assert result["settled_by"] == "deterministic"

    def test_real_error_is_rejected_by_the_validator_before_the_judge_is_needed(self, key_drill):
        case = key_drill["test_fixtures"]["case_real_error"]
        validation = get_validation_for(case["decision"], fake_validator_accepts_everything_structurally_sound)

        assert validation["accepted"] is False

        def judge_that_must_not_run(decision, validation, answer_key):
            raise AssertionError("a validator rejection must settle the case first")

        result = score_decision(case["decision"], validation, key_drill, judge=judge_that_must_not_run)
        assert result["verdict"] == "incorrect"
        assert result["settled_by"] == "deterministic"

    def test_plausible_alternative_is_accepted_by_the_validator_then_goes_to_the_judge(self, key_drill):
        case = key_drill["test_fixtures"]["case_plausible_alternative"]
        validation = get_validation_for(case["decision"], fake_validator_accepts_everything_structurally_sound)

        assert validation["accepted"] is True

        result = score_decision(case["decision"], validation, key_drill, judge=real_judge)
        assert result["verdict"] == "correct"
        assert result["settled_by"] == "judge"


def test_step2_acceptance_the_validator_is_the_only_source_of_validation_now(key_001, key_drill):
    """The exact claim STEP 2 makes: nowhere in this test does a hand-written
    {"accepted": ...} dict appear — every ValidationResult comes from calling
    a validator, and the fake one can be swapped for the real validation/
    package later without touching scoring.py or judge.py at all.
    """
    cases = [
        {
            "disposition": "REPAIR",
            "repair_id": key_001["repair_must_satisfy"]["reference_repair_id"],
            "patch": {"transforms/stg_orders.sql": "amount_cents / 100.0 AS amount_usd"},
        },
        key_drill["test_fixtures"]["case_plausible_alternative"]["decision"],
        key_drill["test_fixtures"]["case_real_error"]["decision"],
    ]
    keys = [key_001, key_drill, key_drill]

    for decision, key in zip(cases, keys):
        validation = get_validation_for(decision, fake_validator_accepts_everything_structurally_sound)
        result = score_decision(decision, validation, key, judge=real_judge)
        assert result["verdict"] in ("correct", "incorrect")
