"""Tests for grounding.py — C3: authorities that freeze at different times
must be different artifacts.

Mirrors CONFORMANCE.md C3's own test spec: "changing one authority does
not alter the digest of another; each load path verifies its own
artifact." Also exercises the six refusal modes AUTHORITY_LIFECYCLE.md
lists for a bound pair: unfrozen, changed since freezing, wrong filename,
digest moved, bound to the wrong schema version, disagreeing about which
scenario it describes.

Uses tmp_path throughout — never touches the real answer key or grounding
files in this directory.
"""
import json

import pytest
from adii.evaluation.freeze import freeze_answer_key
from adii.evaluation.grounding import build_grounding_key, check_grounding, load_grounding_key

ANSWER_KEY = {"schema_version": "1", "incident_id": "t-1", "correct_disposition": "REPAIR"}


def write_answer_key(tmp_path, name="incident.answer.json", data=None):
    path = tmp_path / name
    path.write_text(json.dumps(data or ANSWER_KEY, indent=2), encoding="utf-8")
    return path


class TestBuildingAGroundingKey:
    def test_cannot_ground_an_unfrozen_answer_key(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        with pytest.raises(FileNotFoundError, match="frozen digest"):
            build_grounding_key(
                answer_key_path, [{"tool": "run_sql", "argument_contains": "amount_cents"}]
            )

    def test_grounding_a_frozen_key_binds_its_current_digest(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        digest = freeze_answer_key(answer_key_path)

        grounding = build_grounding_key(
            answer_key_path, [{"tool": "run_sql", "argument_contains": "amount_cents"}]
        )
        assert grounding["answer_key_digest"] == digest
        assert grounding["answer_key_filename"] == "incident.answer.json"

    def test_malformed_predicate_is_refused_at_build_time(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)

        with pytest.raises(ValueError, match="missing field"):
            build_grounding_key(answer_key_path, [{"tool": "run_sql"}])  # no argument_contains


class TestLoadingAGroundingKey:
    def test_a_correctly_bound_pair_loads(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(
            answer_key_path, [{"tool": "run_sql", "argument_contains": "x"}]
        )
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        loaded = load_grounding_key(grounding_path)
        assert loaded == grounding

    def test_missing_required_field_is_refused(self, tmp_path):
        grounding_path = tmp_path / "bad.grounding.json"
        grounding_path.write_text(json.dumps({"schema_version": "1"}), encoding="utf-8")

        with pytest.raises(ValueError, match="missing required field"):
            load_grounding_key(grounding_path)

    def test_unknown_grounding_schema_version_is_refused(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(answer_key_path, [])
        grounding["schema_version"] = "99"
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        with pytest.raises(ValueError, match="not the known grounding schema version"):
            load_grounding_key(grounding_path)

    def test_grounding_key_naming_a_nonexistent_answer_key_is_refused(self, tmp_path):
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(answer_key_path, [])
        answer_key_path.unlink()  # the answer key file is now gone
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        with pytest.raises(FileNotFoundError):
            load_grounding_key(grounding_path)

    def test_answer_key_changed_since_grounding_was_authored_is_refused(self, tmp_path):
        # This is C3's core reproduction case: the answer key moves after
        # the grounding key was bound to it. Loading must catch the
        # mismatch, never silently pair the grounding key with new content.
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(
            answer_key_path, [{"tool": "run_sql", "argument_contains": "x"}]
        )
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        # The answer key is edited in place (its own .sha256 is now stale
        # too, but that is C2's concern — this test is about grounding
        # catching the drift independently, via its own bound digest).
        mutated = dict(ANSWER_KEY, correct_disposition="NO_REPAIR")
        answer_key_path.write_text(json.dumps(mutated), encoding="utf-8")

        with pytest.raises(ValueError, match="changed since this grounding key was authored"):
            load_grounding_key(grounding_path)

    def test_grounding_key_re_pointed_at_a_different_scenario_is_refused(self, tmp_path):
        # A grounding key's answer_key_digest was computed against one
        # scenario; if the file at answer_key_filename is later replaced
        # by an unrelated (even if internally valid, even if frozen)
        # answer key, the digest mismatch must still catch it — the
        # pairing is by digest, never by filename or trust.
        key_a_path = write_answer_key(tmp_path, "incident.answer.json", ANSWER_KEY)
        freeze_answer_key(key_a_path)
        grounding = build_grounding_key(key_a_path, [{"tool": "run_sql", "argument_contains": "x"}])
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        different_scenario = {
            "schema_version": "1",
            "incident_id": "totally-different",
            "correct_disposition": "ESCALATE",
        }
        key_a_path.unlink()
        (key_a_path.parent / (key_a_path.name + ".sha256")).unlink()
        key_a_path.write_text(json.dumps(different_scenario), encoding="utf-8")
        freeze_answer_key(key_a_path)

        with pytest.raises(ValueError, match="changed since this grounding key was authored"):
            load_grounding_key(grounding_path)


class TestAuthoritiesFreezeIndependently:
    def test_freezing_an_answer_key_does_not_touch_an_unrelated_grounding_key(self, tmp_path):
        # C3's own test spec: "changing one authority does not alter the
        # digest of another." Freeze two independent answer keys; changing
        # one's digest must never affect the other's grounding pairing.
        key_a = write_answer_key(tmp_path, "a.answer.json", dict(ANSWER_KEY, incident_id="a"))
        key_b = write_answer_key(tmp_path, "b.answer.json", dict(ANSWER_KEY, incident_id="b"))
        freeze_answer_key(key_a)
        freeze_answer_key(key_b)

        grounding_a = build_grounding_key(key_a, [{"tool": "run_sql", "argument_contains": "a"}])

        # Mutate b after the fact — a's grounding key must be unaffected.
        key_b.unlink()
        (key_b.parent / (key_b.name + ".sha256")).unlink()
        key_b.write_text(json.dumps(dict(ANSWER_KEY, incident_id="b-changed")), encoding="utf-8")
        freeze_answer_key(key_b)

        grounding_a_path = tmp_path / "a.grounding.json"
        grounding_a_path.write_text(json.dumps(grounding_a), encoding="utf-8")

        # a's grounding key still loads cleanly — b's change is irrelevant.
        loaded = load_grounding_key(grounding_a_path)
        assert loaded["answer_key_filename"] == "a.answer.json"

    def test_each_load_path_verifies_only_its_own_artifact(self, tmp_path):
        # load_grounding_key does not re-run freeze.py's own digest check
        # on the answer key as a frozen-answer-key load — it does its own,
        # independent digest comparison. Corrupting the answer key's
        # .sha256 file (C2's own pin) must not be what grounding relies on.
        answer_key_path = write_answer_key(tmp_path)
        freeze_answer_key(answer_key_path)
        grounding = build_grounding_key(
            answer_key_path, [{"tool": "run_sql", "argument_contains": "x"}]
        )
        grounding_path = tmp_path / "incident.grounding.json"
        grounding_path.write_text(json.dumps(grounding), encoding="utf-8")

        # Corrupt C2's own digest file — grounding's load path must not
        # depend on it at all, since it carries its own copy of the digest.
        (tmp_path / "incident.answer.json.sha256").write_text("garbage", encoding="utf-8")

        loaded = load_grounding_key(grounding_path)
        assert loaded["answer_key_digest"] == grounding["answer_key_digest"]


class TestCheckingGroundingAgainstATrace:
    def test_a_trace_satisfying_every_predicate_is_grounded(self):
        grounding_key = {
            "required_tool_calls": [
                {"tool": "run_sql", "argument_contains": "amount_cents"},
                {"tool": "get_schema", "argument_contains": "stg_orders"},
            ]
        }
        trace = [
            {"tool": "run_sql", "arguments": {"query": "SELECT amount_cents FROM orders"}},
            {"tool": "get_schema", "arguments": {"table": "stg_orders"}},
        ]
        result = check_grounding(trace, grounding_key)
        assert result == {"grounded": True, "missing": []}

    def test_a_trace_missing_one_predicate_names_it(self):
        grounding_key = {
            "required_tool_calls": [
                {"tool": "run_sql", "argument_contains": "amount_cents"},
                {"tool": "get_schema", "argument_contains": "stg_orders"},
            ]
        }
        trace = [{"tool": "run_sql", "arguments": {"query": "SELECT amount_cents FROM orders"}}]
        result = check_grounding(trace, grounding_key)
        assert result["grounded"] is False
        assert result["missing"] == [{"tool": "get_schema", "argument_contains": "stg_orders"}]

    def test_an_empty_trace_against_no_requirements_is_grounded(self):
        assert check_grounding([], {"required_tool_calls": []}) == {"grounded": True, "missing": []}
