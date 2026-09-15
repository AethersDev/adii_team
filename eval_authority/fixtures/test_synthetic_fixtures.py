"""Scorer tests for synthetic fixtures — deliberately separate from the
walkthrough tests (test_step1_all.py, test_step2_all.py), which only ever
exercise demo-learning-* (REPAIR-disposition) cases.

These fixtures cover dispositions the walkthrough never exercises:
NO_REPAIR and ESCALATE. Both settle deterministically (scoring.py's
non-REPAIR short-circuit), so no judge agent is involved here.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scoring import score_decision

HERE = Path(__file__).parent


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def key_no_repair():
    return load("synthetic-no-repair-001.answer.json")


@pytest.fixture(scope="module")
def key_escalate():
    return load("synthetic-escalate-001.answer.json")


def run_case(key: dict, case_name: str) -> dict:
    case = key["test_fixtures"][case_name]
    return score_decision(case["decision"], case["validation"], key)


def test_no_repair_correct_case_settles_deterministically(key_no_repair):
    case = key_no_repair["test_fixtures"]["case_correct_no_repair"]
    result = run_case(key_no_repair, "case_correct_no_repair")
    assert result == case["expected_score_decision_result"]


def test_no_repair_wrong_repair_proposed_is_incorrect(key_no_repair):
    case = key_no_repair["test_fixtures"]["case_wrong_repair_proposed"]
    result = run_case(key_no_repair, "case_wrong_repair_proposed")
    assert result == case["expected_score_decision_result"]


def test_escalate_correct_case_settles_deterministically(key_escalate):
    case = key_escalate["test_fixtures"]["case_correct_escalate"]
    result = run_case(key_escalate, "case_correct_escalate")
    assert result == case["expected_score_decision_result"]


def test_escalate_guessed_instead_is_incorrect(key_escalate):
    case = key_escalate["test_fixtures"]["case_guessed_instead_of_escalating"]
    result = run_case(key_escalate, "case_guessed_instead_of_escalating")
    assert result == case["expected_score_decision_result"]
