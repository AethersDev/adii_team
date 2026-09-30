"""The evaluation report (final plan 6.1, decision Q): written from the packs' reports alone,
the three claims apart, every failure named, and earned authority computed exactly as it was
registered before any final run."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "evaluation_report.py"
spec = importlib.util.spec_from_file_location("evaluation_report", SCRIPT)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def run(label, truth, answered, category, arm="full", admissible=False):
    return {"label": label, "incident": label, "arm": arm, "repeat": 1, "truth": truth,
            "tier": "explicit", "termination": "submitted", "disposition": answered,
            "category": category, "decisive": True, "validation": None,
            "admissible": admissible, "cost_usd": 0.01, "latency_ms": 50000}


def test_the_bound_is_the_exact_clopper_pearson_one_and_29_all_right_is_what_earns():
    assert report.lower_bound(4, 4) == pytest.approx(0.05 ** (1 / 4), abs=1e-6)     # 0.47
    assert report.lower_bound(12, 12) == pytest.approx(0.05 ** (1 / 12), abs=1e-6)   # 0.78
    assert report.lower_bound(9, 10) == pytest.approx(0.6058, abs=1e-3)       # a known value
    assert report.lower_bound(0, 5) == 0.0
    assert report.needed() == 29
    assert report.lower_bound(28, 28) < report.FLOOR <= report.lower_bound(29, 29)


def test_a_class_is_earned_only_with_enough_right_decisions_and_no_wrong_one_admitted():
    fixes = [run(f"f{i}", "REPAIR", "REPAIR", "success", admissible=True) for i in range(29)]
    [fix, leave, escalate] = report.earned(fixes)
    assert (fix["made"], fix["right"], fix["earned"]) == (29, 29, True)
    assert (leave["made"], leave["earned"]) == (0, False)          # nothing decided, nothing earned
    wrong = run("w", "NO_REPAIR", "REPAIR", "false_repair", admissible=True)
    assert report.earned(fixes + [wrong])[0]["wrong_admitted"] == 1
    assert report.earned(fixes + [wrong])[0]["earned"] is False    # one wrong fix admitted: none
    assert report.earned(fixes[:4])[0]["earned"] is False          # four right: 0.47, not earned


def test_the_report_keeps_the_claims_apart_names_every_failure_and_says_what_did_not_run():
    sol = {"runs": [run("s-full-1", "REPAIR", "REPAIR", "success", admissible=True),
                    run("s-full-2", "NO_REPAIR", "ESCALATE", "unnecessary_escalation"),
                    run("s-alert-1", "REPAIR", "ESCALATE", "unnecessary_escalation",
                        arm="alert-only"),
                    run("s-floor-1", "ESCALATE", "ESCALATE", "correct_abstention",
                        arm="always-escalate")], "unscored": []}
    freeze = {"name": "freeze-x", "digest": "ab" * 32, "source_revision": "c0ffee",
              "packs": {"final-sol": {"model": "gpt-6-sol", "arms": ["full"], "incidents": ["i"],
                                      "max_turns": 20, "max_tokens": 4096,
                                      "max_cost_usd": 0.5, "pack_cap_usd": 1.0}}}
    text, results = report.write({"final-sol": sol}, {"final-sol": freeze})
    assert "## Claim 1" in text and "## Claim 2" in text and "## Claim 3" in text
    assert "| gpt-6-sol | 1/2 |" in text and "| alert only | 0/1 |" in text
    assert "`s-full-2`" in text and "`s-alert-1`" in text and "`s-full-1`" not in text
    assert "**Not run yet:** final-luna, final-gpt-4-1, final-held-out." in text
    assert "| gpt-4.1 | not run |" in text
    assert results == {"freeze": "freeze-x · sha256 abababababab", "sol_full_correct": "1",
                       "sol_full_false_admits": "0", "sol_alert_only_correct": "0",
                       "sol_alert_only_false_admits": "0", "floor_correct": "1",
                       # the floor spends nothing, so three of the four runs are paid; one fix
                       # was proposed, and it was right
                       "paid_runs": "3", "all_repair_proposals": "1", "all_wrong_repairs": "0",
                       "all_false_admits": "0"}


def test_the_committed_report_is_what_the_packs_and_their_own_freeze_produce():
    """Each pack is reported under the freeze its receipt names. A newer freeze registers more
    packs (the local extension, with no pack cap); stamping the newest on decision E's four
    misstated which system they ran on, and no longer even rendered."""
    reports = {p.name.removesuffix(".report.json"): json.loads(p.read_text(encoding="utf-8"))
               for p in sorted(report.PACKS.glob("final-*.report.json"))}
    freezes = report.freezes_of(list(reports))
    assert {f["name"] for f in freezes.values()} == {"freeze-2026-09-26"}
    text, _ = report.write(reports, freezes)
    assert text == report.OUT.read_text(encoding="utf-8")
