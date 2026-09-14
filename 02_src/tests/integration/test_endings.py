"""One committed record per way a run can end besides success, each produced by the runtime
and each rendering to its committed report. Inherited D11: a rejected repair, a model
failure, a bound and an infrastructure failure read as legibly as a success, in their own
terms — and a call the run died on is unanswered, never pending."""
from __future__ import annotations

from dataclasses import replace

from adii.examples.endings import ENDINGS, endings, main
from adii.reporting import read_record, render_run

LABELLED = {
    "repair-rejected": "  REJECTED   (decided by the validator, never by the agent)",
    "model-failure": "RUN ENDED — MODEL FAILURE",
    "bound-hit": "RUN ENDED — BOUND HIT",
    "infrastructure-failure": "RUN ENDED — INFRASTRUCTURE FAILURE",
}


def test_each_ending_is_committed_as_the_runtime_produces_it(capsys):
    produced = endings()
    assert set(produced) == set(LABELLED)
    for label, fresh in produced.items():
        committed = read_record(ENDINGS / label / "record.json")
        assert replace(committed, provenance={}, latency_ms=0) == \
            replace(fresh, provenance={}, latency_ms=0), label


def test_each_ending_renders_to_its_committed_report_in_its_own_terms():
    reports = {label: render_run(read_record(ENDINGS / label / "record.json"))
               for label in LABELLED}
    for label, line in LABELLED.items():
        assert line in reports[label], label
        assert reports[label] == (ENDINGS / label / "report.txt").read_text(encoding="utf-8")
        assert "pending" not in reports[label].lower()
    assert "  <- (unanswered: the run ended here)" in reports["infrastructure-failure"]
    assert "never reached" in reports["bound-hit"]


def test_the_generator_writes_every_ending(tmp_path, capsys):
    assert main(["--into", str(tmp_path)]) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(LABELLED)
    assert (tmp_path / "bound-hit" / "report.txt").is_file()
