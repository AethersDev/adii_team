"""Every sentence the inspector adds to a record is a deterministic projection of record
fields, and lives in one file, phrasing.js. These tests pin each projection against the
committed records — one per way a run can end — by evaluating the dictionary in node, so
the mapping the README lists is the mapping the page uses. A sentence that adds a cause
the record does not state fails here."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WEB = ROOT / "02_src" / "adii" / "demo" / "web"
WALKTHROUGH = ROOT / "01_data" / "walkthrough"
RECORDS = {
    "accepted": WALKTHROUGH / "record.json",
    "rejected": WALKTHROUGH / "endings" / "repair-rejected" / "record.json",
    "bound": WALKTHROUGH / "endings" / "bound-hit" / "record.json",
    "model": WALKTHROUGH / "endings" / "model-failure" / "record.json",
    "infra": WALKTHROUGH / "endings" / "infrastructure-failure" / "record.json",
}
# Words that assert a cause the record does not state, or that link the steps to the
# decision as if one followed from the other — a scripted investigator conditions on
# nothing, so the page may only say what happened, then what was submitted.
FORBIDDEN = ("could not", "couldn't", "insufficient", "stuck", "gave up", "unable", "confused",
             "because", "therefore", "based on", "concluded", "evidence showed", "so it decided",
             # words that grant an authority the record does not: nothing on the page is safe,
             # confirmed, correct or verified unless the record's own fields establish it
             "safe", "confirmed", "correctly", "verified", "guaranteed", "the system")


def node() -> str:
    found = shutil.which("node")
    if not found:
        pytest.skip("node is not installed; the phrasing projections are evaluated in it")
    return found


def phrase(kind: str, key: str, record: dict) -> str:
    """Evaluate PHRASING[kind][key] against a record, in node, exactly as the page does."""
    script = (f"{(WEB / 'phrasing.js').read_text(encoding='utf-8')}\n"
              f"const r = {json.dumps(record)};\n"
              f"const f = PHRASING[{kind!r}][{key!r}];\n"
              "process.stdout.write(typeof f === 'function' ? f(r) : f);")
    # UTF-8 on both ends: the projections carry an em dash and a middle dot, and Windows
    # would otherwise decode node's output as cp1252.
    return subprocess.run([node(), "-e", script], capture_output=True, text=True,
                          encoding="utf-8", check=True, timeout=30).stdout


def load(name: str) -> dict:
    return json.loads(RECORDS[name].read_text(encoding="utf-8"))


@pytest.mark.parametrize(("name", "expected"), [
    ("accepted", "The investigator committed to REPAIR."),
    ("bound", "The investigator reached a bound it set after 0 model turns and 3 tool calls, "
              "and stopped without a decision."),
    ("model", "The model failed and the run stopped without a decision."),
    ("infra", "Something outside the model failed — the runtime or the provider, not the "
              "model's — and the run "
              "stopped without a decision."),
])
def test_how_a_run_ended_is_a_projection_of_its_fields(name, expected):
    record = load(name)
    assert phrase("ended", record["termination"], record) == expected


@pytest.mark.parametrize(("name", "expected"), [
    ("accepted", "REPAIR · accepted · scripted verdict"),
    ("rejected", "REPAIR · not accepted · scripted verdict"),
    ("bound", "Stopped at its limit, no decision"),
    ("model", "Stopped: the model failed, no decision"),
    ("infra", "Stopped: a failure outside the model, no decision"),
])
def test_the_short_outcome_inherits_exactly_the_records_authority(name, expected):
    """The committed records are scripted (configuration.model null), so their verdicts are
    presets and the label says so; nothing here reads as the validator's."""
    record = load(name)
    assert phrase("outcome", record["termination"], record) == expected


def turn_text(kind: str, key: str, *args) -> str:
    """Evaluate PHRASING.turn[key](*args) in node, exactly as the page does."""
    script = (f"{(WEB / 'phrasing.js').read_text(encoding='utf-8')}\n"
              f"const f = PHRASING[{kind!r}][{key!r}];\n"
              f"const a = {json.dumps(list(args))};\n"
              "process.stdout.write(typeof f === 'function' ? f(...a) : f);")
    return subprocess.run([node(), "-e", script], capture_output=True, text=True,
                          encoding="utf-8", check=True, timeout=30).stdout


def test_a_turn_says_what_was_asked_and_what_came_back_quoting_only_the_payload():
    record = load("accepted")
    calls = [e["payload"] for e in record["trace"] if e["kind"] == "tool_call"]
    results = [e["payload"] for e in record["trace"] if e["kind"] == "tool_result"]
    assert turn_text("turn", "asked", calls[0]["name"], calls[0]["arguments"]) == \
        "Asked the tool layer to run get_schema with table = orders"
    assert turn_text("turn", "answered", results[0]) == "answered with 3 columns"
    refused = next(r for r in results if r["status"] == "DENIED")
    assert turn_text("turn", "answered", refused).startswith("refused: unknown tool")
    assert turn_text("turn", "decided", "REPAIR") == "Committed to REPAIR"
    assert turn_text("turn", "rejected", {"rejection_class": "invalid_envelope",
                                          "reason": "not one of the three message forms"}) == \
        "The submission was rejected (invalid_envelope): not one of the three message forms"
    checked = {"accepted": False, "report": "no", "checks_run": ["rebuild"]}
    assert turn_text("turn", "validated", {**checked, "accepted": True}) == \
        "The validator accepted the repair"
    assert turn_text("turn", "validated", checked) == "The validator did not accept the repair"
    assert turn_text("turn", "validated", {**checked, "checks_run": []}) == \
        "No validator checked the repair"
    # a scripted run's verdict is a preset: the turn says so, and "not checked" stays nobody's
    assert turn_text("turn", "validated", {**checked, "accepted": True}, True) == \
        "The scripted verdict accepted the repair"
    assert turn_text("turn", "validated", checked, True) == \
        "The scripted verdict did not accept the repair"
    assert turn_text("turn", "validated", {**checked, "checks_run": []}, True) == \
        "No validator checked the repair"


@pytest.mark.parametrize(("name", "expected"), [
    ("accepted", "Decided: REPAIR — accepted · scripted verdict"),
    ("rejected", "Decided: REPAIR — not accepted · scripted verdict"),
    ("bound", "Stopped at its limit, no decision"),
    ("model", "Stopped: the model failed, no decision"),
    ("infra", "Stopped: a failure outside the model, no decision"),
])
def test_the_headline_inherits_exactly_the_records_authority(name, expected):
    record = load(name)
    assert phrase("headline", record["termination"], record) == expected


def test_a_verdict_names_who_produced_it():
    """Verdict provenance is one field, configuration.model: null is a scripted run whose ACCEPT
    or REJECT was written by hand and is labelled a scripted verdict everywhere — card,
    headline, section title, owner line, turn; a model's run with checks run carries the
    validator's; "not checked" is nobody's verdict on either. A screenshot of a preset can
    never read as the validator having computed it."""
    scripted = load("accepted")
    computed = {**scripted, "configuration": {**scripted["configuration"], "model": "a-model"}}
    assert phrase("headline", "submitted", scripted) == \
        "Decided: REPAIR — accepted · scripted verdict"
    assert phrase("headline", "submitted", computed) == \
        "Decided: REPAIR — accepted by the validator"
    assert phrase("outcome", "submitted", computed) == "REPAIR · accepted by the validator"
    assert phrase("validation", "title", scripted) == "What the scripted verdict said"
    assert phrase("validation", "title", computed) == "What the validator said"
    assert phrase("validation", "said", scripted) == \
        "The scripted verdict, written by hand, accepted the repair."
    assert phrase("validation", "said", computed) == "The validator accepted the repair."
    assert phrase("by", "validator", scripted).startswith("Scripted verdict, written by hand")
    assert phrase("by", "validator", computed) == "Asserted by the validator, not ADII"
    assert phrase("by", "investigator", scripted).startswith("Scripted decision, written by hand")
    assert phrase("by", "investigator", computed) == "Asserted by ADII, the investigator"
    assert phrase("by", "proposed", scripted).endswith("Not applied by anyone.")
    assert phrase("by", "proposed", computed) == \
        "Proposed by ADII, the investigator. Not applied by anyone."
    unchecked = {**computed, "validation": {"accepted": False, "checks_run": [], "report": "no"}}
    for record in (unchecked, {**unchecked, "configuration": scripted["configuration"]}):
        assert phrase("headline", "submitted", record) == \
            "Decided: REPAIR — not checked by a validator"
        # no validator spoke, so the section is not attributed to one, on either kind of run
        assert phrase("validation", "title", record) == "Validation"
        assert phrase("validation", "said", record) == "No validator checked the repair."
        assert phrase("by", "validator", record) == \
            "Recorded by the runtime: no validator checked it"
    source = (WEB / "app.js").read_text(encoding="utf-8")
    for literal in ("Asserted by the validator", "Asserted by ADII", "May write", "never saw"):
        assert literal not in source, \
            f"app.js writes {literal!r} itself instead of reading the dictionary"
    assert "PHRASING.verdictLabelOf(row.validation, row.model)" in source, \
        "a run-list card labels a verdict without its provenance"


def test_declared_paths_are_never_called_enforced():
    """The incident's permitted paths are text the investigator is told; nothing enforces them
    yet, and the page says exactly that beside them — never "may write"."""
    assert phrase("product", "declaredPaths", {}) == "Declared permitted paths"
    assert phrase("product", "declaredNone", {}) == "none declared"
    assert phrase("product", "declaredPathsHint", {}) == \
        "Declared to the investigator as text. Nothing enforces it yet."
    for key in ("declaredPaths", "declaredPathsHint", "declaredNone"):
        assert f"PHRASING.product.{key}" in (WEB / "app.js").read_text(encoding="utf-8")


def test_the_keys_are_named_for_what_they_are():
    """Scored against a frozen key the authority holds — the scorer refuses an unfrozen one —
    and the keys are team-authored development keys; no page calls one ground truth."""
    assert phrase("evaluation", "by", {}) == \
        "Scored by the evaluation authority against a frozen answer key it holds"
    assert phrase("evaluation", "keys", {}) == \
        "Development keys are team-authored and frozen by digest. No unseen key exists."
    source = (WEB / "phrasing.js").read_text(encoding="utf-8").lower()
    for word in ("ground truth", "independent truth", "benchmark", "never saw"):
        assert word not in source, word


def test_refusals_are_counted_beside_observations():
    """Every tool attempt is counted; the refused ones (DENIED, REJECTED) and the failed ones
    (ERROR) beside the answered, so a run of twelve attempts is never shown as eight
    observations and nothing more; a refusal is neither a success nor a failure of the model."""
    script = (f"{(WEB / 'phrasing.js').read_text(encoding='utf-8')}\n"
              "process.stdout.write([PHRASING.product.attempts(12, 8, 4, 0), "
              "PHRASING.product.attempts(3, 3, 0, 0), PHRASING.product.attempts(1, 0, 0, 1), "
              "PHRASING.product.nothingAnswered(2), "
              "PHRASING.product.nothingAnswered(1)].join('|'));")
    out = subprocess.run([node(), "-e", script], capture_output=True, text=True,
                         encoding="utf-8", check=True, timeout=30).stdout
    assert out.split("|") == [
        "12 tool attempts · 8 observations · 4 refused", "3 tool attempts · 3 observations",
        "1 tool attempt · 0 observations · 1 failed",
        "It looked at nothing before deciding: 2 requests, none answered.",
        "It looked at nothing before deciding: 1 request, none answered."]
    record = load("accepted")            # three answered, one DENIED, in the committed trace
    statuses = [e["payload"]["status"] for e in record["trace"] if e["kind"] == "tool_result"]
    assert statuses.count("OK") == 3 and statuses.count("DENIED") == 1
    assert "PHRASING.product.attempts(requests, looked.length, refused, failed)" in \
        (WEB / "app.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("name", list(RECORDS))
def test_every_sentence_the_page_adds_is_recoverable_from_the_record_alone(name):
    """The reviewer's test for the whole dictionary: hand someone record.json without the page,
    and every factual sentence the page adds must be recoverable from it. So every projection
    that takes a record is evaluated against every committed record, and none may carry a
    word that grants an authority, a cause or a quality the record does not state."""
    record = load(name)
    projections = [phrase("ended", record["termination"], record),
                   phrase("outcome", record["termination"], record),
                   phrase("headline", record["termination"], record),
                   phrase("by", "investigator", record), phrase("by", "proposed", record),
                   phrase("by", "runtime", record),
                   phrase("evaluation", "by", record), phrase("evaluation", "keys", record),
                   phrase("product", "declaredPathsHint", record),
                   *(turn_text("turn", "answered", e["payload"])
                     for e in record["trace"] if e["kind"] == "tool_result")]
    if record["validation"]:       # the page draws the validator's section only then
        projections += [phrase("validation", "title", record), phrase("validation", "said", record),
                        phrase("by", "validator", record)]
    if record["decision"]:
        projections.append(phrase("action", record["decision"]["disposition"], record))
    text = " ".join(projections).lower()
    hits = [w for w in FORBIDDEN if w in text]
    assert not hits, f"a projection grants what the record does not state: {hits}"


def test_a_repair_nobody_checked_is_not_called_rejected():
    """A validation result with `checks_run` empty states that no check ran; the record's
    own placeholder verdict says so in its report. The page must not read `accepted: false`
    as a verdict against the repair — that would assert a finding the record disclaims."""
    record = load("rejected")
    record["validation"] = {"accepted": False, "checks_run": [],
                            "report": "No independent validator exists yet."}
    assert phrase("headline", "submitted", record) == "Decided: REPAIR — not checked by a validator"
    assert phrase("outcome", "submitted", record) == "REPAIR · not checked by a validator"


@pytest.mark.parametrize("name", list(RECORDS))
def test_no_projection_asserts_a_cause_the_record_does_not_state(name):
    record = load(name)
    text = " ".join([phrase("ended", record["termination"], record),
                     phrase("outcome", record["termination"], record),
                     phrase("headline", record["termination"], record),
                     *(turn_text("turn", "answered", e["payload"])
                       for e in record["trace"] if e["kind"] == "tool_result")]).lower()
    hits = [w for w in FORBIDDEN if w in text]
    assert not hits, f"a projection asserts a cause the record does not state: {hits}"


def test_the_evaluations_categories_are_said_in_the_authoritys_own_terms():
    """One sentence per category, from outcome_classification.py's definitions; the
    category itself is always shown beside it, so the sentence never replaces it."""
    from adii.evaluation.outcome_classification import CATEGORIES
    for category in (*CATEGORIES, "not_evaluable"):
        assert phrase("evaluation", category, {}).endswith("."), category
    assert phrase("evaluation", "success", {}) == "The decision matched the answer key."


def test_the_cost_is_a_labelled_lower_bound_never_a_zero_for_a_paid_run():
    """Inherited D15 on the page: a run with no paid provider spent nothing and says so; a
    paid run shows the ledger's lower bound and counts the requests it could not price."""
    record = {**load("accepted"), "configuration": {"provider": "scripted", "model": None}}
    record["counters"] = {**record["counters"], "api_cost_usd": 0.0}
    paid = {**record, "configuration": {"provider": "openai"},
            "counters": {**record["counters"], "api_cost_usd": 0.0012},
            "trace": [{"sequence": 0, "kind": "model_requested", "payload": {"turn": 1}},
                      {"sequence": 1, "kind": "model_responded",
                       "payload": {"turn": 1, "usage": {"prompt_tokens": 100}}},
                      {"sequence": 2, "kind": "model_requested", "payload": {"turn": 2}}]}
    script = (f"{(WEB / 'phrasing.js').read_text(encoding='utf-8')}\n"
              f"process.stdout.write(PHRASING.cost({json.dumps(record)}) + '|' + "
              f"PHRASING.cost({json.dumps(paid)}));")
    out = subprocess.run([node(), "-e", script], capture_output=True, text=True,
                         encoding="utf-8", check=True, timeout=30).stdout
    assert out == "nothing spent (no paid provider)|at least $0.0012 (1 request(s) without usage)"


def test_a_run_without_a_model_is_always_marked_scripted():
    """Projected from one field, configuration.model, so no screenshot of a scripted run
    can pass for a model result."""
    expected = "Scripted investigator · development demonstration, not a model result"
    assert phrase("product", "scripted", {}) == expected
    source = (WEB / "app.js").read_text(encoding="utf-8")
    assert "scriptedNote(cfg.model)" in source, "the run page does not show the scripted note"


def test_the_answer_first_sentences_are_projections_of_the_decision_and_the_trace():
    """The action is the disposition's meaning as an instruction and nothing more; what it
    looked at is counted from answered requests; the live counter from the trace so far."""
    for disposition, expected in (
            ("NO_REPAIR", "Do not change the data or the pipeline."),
            ("ESCALATE", "Hand this to a person. The evidence gathered does not settle it."),
            ("REPAIR", "A change was proposed. Nobody has applied it; it is shown below, and "
                       "until a validator accepts it, it stays a proposal.")):
        assert phrase("action", disposition, {}) == expected
    script = (f"{(WEB / 'phrasing.js').read_text(encoding='utf-8')}\n"
              "process.stdout.write([PHRASING.product.looked(1), PHRASING.product.looked(3), "
              "PHRASING.product.lookedAtNothing, PHRASING.product.soFar(1, 0), "
              "PHRASING.product.soFar(4, 3), "
              "PHRASING.product.runsWith('m', 'local', undefined, 12), "
              "PHRASING.product.runsWith('gpt-4.1', 'openai', 0.25, 20)].join('|'));")
    out = subprocess.run([node(), "-e", script], capture_output=True, text=True,
                         encoding="utf-8", check=True, timeout=30).stdout
    assert out.split("|") == [
        "1 observation", "3 observations",
        "It looked at nothing before deciding: no request was answered.",
        "1 request so far · 0 answered.", "4 requests so far · 3 answered.",
        "Runs with m on this machine · 12 turns. One investigation at a time.",
        "Runs with gpt-4.1 at a paid provider · up to $0.25 · 20 turns. "
        "One investigation at a time."]
    text = " ".join(phrase("action", d, {}) for d in ("NO_REPAIR", "ESCALATE", "REPAIR")).lower()
    assert not [w for w in FORBIDDEN if w in text]


def test_the_readme_lists_every_sentence_the_page_adds():
    """The dictionary is reviewable because the README names every entry. A new entry
    without a README line is a sentence the team never saw."""
    readme = (ROOT / "02_src" / "adii" / "demo" / "README.md").read_text(encoding="utf-8")
    source = (WEB / "phrasing.js").read_text(encoding="utf-8")
    for key in ("submitted", "bound_hit", "model_failure", "infrastructure_failure",
                "notInvoked", "asked", "answered", "wrote", "decided", "validated",
                "unanswered", "rejected", "scripted", "cost", "runtime", "success",
                "correct_abstention",
                "unnecessary_escalation", "false_repair", "repair_rejection", "failure",
                "not_evaluable", "action", "looked", "lookedAtNothing", "soFar",
                "attempts", "nothingAnswered", "declaredPaths", "declaredNone",
                "declaredPathsHint", "scriptedRun", "by", "verdictLabelOf", "title", "said",
                "scriptedAccepted", "scriptedRejected", "keys"):
        assert key in source, f"phrasing.js lost {key}"
        assert f"`{key}`" in readme, f"README does not list the {key} sentence"
