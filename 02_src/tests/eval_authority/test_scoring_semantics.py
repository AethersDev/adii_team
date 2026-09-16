"""C6: scoring semantics changes are pre-registered, never post-hoc.

CONFORMANCE.md C6 — "the scoring definition carries a version and a
freeze date; a test asserts the frozen definition is the one the scorer
implements." This test loads scoring_semantics.json through the same
frozen-digest loader C2 built (freeze.py), so the semantics document
itself cannot silently drift either — and then checks two things no other
test file checks: that every rule's "implemented_by" name still resolves
to a real, callable attribute in this codebase (catching a rename or
removal the frozen document was never updated for), and that each rule's
own "statement" text is echoed by scoring.py/judge.py's own docstrings —
not merely that the code behaves a certain way (test_step1_all.py and
test_edge_cases.py already prove that in depth) but that the frozen
document and the code's own self-description have not drifted apart.

If a future change to scoring.py's behavior is intentional, the correct
order is: write scoring_semantics.json version 2 (a new file, e.g.
scoring_semantics.v2.json — never edit this one in place), freeze it,
change the code, and this test file grows a new class for the new rule.
Changing this test to match new code without a new frozen document first
is exactly the post-hoc reinterpretation C6 exists to prevent.
"""
import importlib
from pathlib import Path
from typing import ClassVar

import pytest
from adii.evaluation.freeze import load_frozen_answer_key

EVALUATION_DIR = Path(__file__).resolve().parents[2] / "adii" / "evaluation"
SEMANTICS = load_frozen_answer_key(EVALUATION_DIR / "scoring_semantics.json")
RULES_BY_ID = {rule["id"]: rule for rule in SEMANTICS["rules"]}


def resolve(dotted_name: str):
    """Resolve "adii.evaluation.module.attr" to the real object — importing
    eval_authority's own modules, so this stays a check of THIS codebase's
    own promise to its frozen document, not a second copy of
    test_contract_consistency.py.
    """
    parts = dotted_name.split(".")
    for i in range(len(parts), 0, -1):
        module_name = ".".join(parts[:i])
        try:
            obj = importlib.import_module(module_name)
        except ImportError:
            continue
        for part in parts[i:]:
            obj = getattr(obj, part)
        return obj
    raise ImportError(f"could not resolve {dotted_name!r}")


class TestFrozenDocumentItself:
    def test_semantics_document_is_frozen_and_unmodified(self):
        assert SEMANTICS["semantics_version"] == "1"
        assert SEMANTICS["frozen_at"] == "2026-09-15"

    def test_every_rule_names_the_code_it_governs(self):
        for rule in SEMANTICS["rules"]:
            assert rule["implemented_by"], f"{rule['id']} names no implementing code"


class TestEveryRuleResolvesToRealCode:
    """The check RULES_BY_ID exists to drive: does "implemented_by" still
    point at something real? A rename or deletion in scoring.py/judge.py
    that nobody updated this frozen document for is exactly the kind of
    silent drift C6 exists to catch — this fails loudly instead."""

    @pytest.mark.parametrize("rule_id", sorted(RULES_BY_ID))
    def test_implemented_by_resolves(self, rule_id):
        rule = RULES_BY_ID[rule_id]
        for dotted_name in rule["implemented_by"].split(", "):
            resolve(dotted_name)  # raises ImportError/AttributeError if it no longer exists


class TestFrozenStatementsAreEchoedByTheCodeItself:
    """Not "does the code behave this way" (test_step1_all.py and
    test_edge_cases.py already prove that exhaustively) but "does the
    code's own documentation of itself still say the same thing the
    frozen semantics document says" — catching the case where behavior
    and this file both still agree, but the code's docstring (the thing a
    future reader actually reads) has quietly diverged from the frozen
    wording."""

    def test_r1_no_partial_credit_is_stated_in_score_disposition(self):
        doc = resolve("adii.evaluation.scoring.score_disposition").__doc__
        assert "one, right or wrong" in doc or "Nothing in between" in doc

    def test_r2_validation_gate_is_stated_in_score_repair_validation(self):
        doc = resolve("adii.evaluation.scoring.score_repair_validation").__doc__
        assert "independently accepted" in doc

    def test_r3_both_fields_required_is_stated_in_decide_route(self):
        doc = resolve("adii.evaluation.scoring.decide_route").__doc__
        assert "root_cause_id" in doc and "repair_id" in doc

    def test_r4_scope_limit_is_stated_in_the_judge_prompt_template(self):
        template = resolve("adii.evaluation.judge.JUDGE_PROMPT_TEMPLATE")
        assert "outside your scope" in template

    def test_r5_word_boundary_is_stated_in_parse_judge_reply(self):
        # The word-boundary behavior itself is documented as an inline
        # comment rather than the docstring — resolve the source instead.
        import inspect
        source = inspect.getsource(resolve("adii.evaluation.judge.parse_judge_reply"))
        assert "word-boundary" in source or "word boundary" in source

    def test_r6_unresolved_reporting_is_stated_in_score_decision(self):
        doc = resolve("adii.evaluation.scoring.score_decision").__doc__
        assert "unresolved" in doc


class TestBehaviorMatchesTheFrozenRuleContent:
    """A small, direct sample tying rule text to behavior — not a
    duplicate of test_step1_all.py's exhaustive coverage, but proof that
    the specific phrase in each frozen statement corresponds to something
    real, for the rules where the statement makes a falsifiable claim
    about a concrete input/output pair."""

    ANSWER_KEY: ClassVar[dict] = {
        "correct_disposition": "REPAIR",
        "correct_root_cause_id": "CAUSE_A",
        "repair_must_satisfy": {"reference_repair_id": "REPAIR_A"},
    }

    def test_r1_claims_no_near_miss_allowance(self):
        assert "no near-miss allowance" in RULES_BY_ID["R1"]["statement"]
        from adii.evaluation.scoring import score_disposition
        assert score_disposition("NO_REPAIR", self.ANSWER_KEY) == "incorrect"

    def test_r3_claims_never_auto_pass_on_only_one_match(self):
        assert "never auto-passed on a match of only one" in RULES_BY_ID["R3"]["statement"]
        from adii.evaluation.scoring import decide_route
        decision = {
            "disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "SOMETHING_ELSE"
        }
        assert decide_route(decision, {"accepted": True}, self.ANSWER_KEY) == "needs_judge_review"

    def test_r6_claims_never_silently_scored(self):
        assert "never silently scored" in RULES_BY_ID["R6"]["statement"]
        from adii.evaluation.scoring import score_decision
        decision = {
            "disposition": "REPAIR", "root_cause_id": "CAUSE_A", "repair_id": "SOMETHING_ELSE"
        }
        result = score_decision(decision, {"accepted": True}, self.ANSWER_KEY, judge=None)
        assert result == {"verdict": "unresolved", "settled_by": "none"}
