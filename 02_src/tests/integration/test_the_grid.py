"""The controlled benchmark's machinery, against the scripted stand-in endpoint: nothing is
spent and no model runs, so every number here is the machinery's, not a result."""
from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer

import pytest
from adii.evaluation import grid

from ..unit.fakes import END
from .fake_model import FakeModel

TWO = sorted(p.name.removesuffix(".answer.json")
             for p in grid.CATALOGUE.glob("*.answer.json"))[:2]


@pytest.fixture
def endpoint():
    FakeModel.script, FakeModel.seen, FakeModel.usage = [], [], None
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()
    httpd.server_close()


def args(tmp_path, endpoint, *more):
    return ["--pack", "t", "--provider", "local", "--model", "m", "--endpoint", endpoint,
            "--incidents", *TWO, "--repeats", "2", "--archive", str(tmp_path / "runs"),
            "--packs", str(tmp_path / "packs"), *more]


def test_every_promised_cell_is_run_scored_and_reported(tmp_path, endpoint):
    FakeModel.script[:] = [END] * 8           # 2 incidents × 2 model arms × 2 repeats
    assert grid.main(args(tmp_path, endpoint)) == 0
    runs = sorted(p.name for p in (tmp_path / "runs").iterdir())
    assert len(runs) == 12                    # and the floor arm, with no model: 3 arms in all
    assert all((tmp_path / "runs" / r / "evaluation_report.json").is_file() for r in runs)
    receipt = json.loads((tmp_path / "packs" / "t.json").read_text(encoding="utf-8"))
    assert receipt["arms"] == ["full", "alert-only", "always-escalate"] and receipt["repeats"] == 2
    result = json.loads((tmp_path / "packs" / "t.report.json").read_text(encoding="utf-8"))
    assert {a: r["runs"] for a, r in result["arms"].items()} == \
        {"full": 4, "alert-only": 4, "always-escalate": 4}
    assert "| full |" in (tmp_path / "packs" / "t.report.md").read_text(encoding="utf-8")
    # the alert-only arm was shown no tool
    alert_only = next(p for p in (tmp_path / "runs").iterdir() if "-alert-only-" in p.name)
    told = json.loads((alert_only / "receipt.json").read_text(encoding="utf-8"))
    assert told["configuration"]["tools"] == [] and told["configuration"]["arm"] == "alert-only"


def test_a_pack_resumes_and_never_runs_a_cell_twice(tmp_path, endpoint):
    FakeModel.script[:] = [END] * 8
    assert grid.main(args(tmp_path, endpoint)) == 0
    asked = len(FakeModel.seen)
    assert grid.main(args(tmp_path, endpoint)) == 0
    assert len(FakeModel.seen) == asked       # nothing was asked again


def test_a_pack_resumed_with_other_terms_is_refused(tmp_path, endpoint, capsys):
    FakeModel.script[:] = [END] * 8
    assert grid.main(args(tmp_path, endpoint)) == 0
    assert grid.main(args(tmp_path, endpoint, "--max-turns", "5")) == 2
    assert "resumes only as it began" in capsys.readouterr().out


def test_a_paid_pack_whose_worst_case_crosses_its_cap_is_refused_before_anything_runs(
        tmp_path, capsys):
    argv = ["--pack", "p", "--provider", "openai", "--model", "gpt-4.1", "--incidents", *TWO,
            "--repeats", "3", "--max-cost-usd", "0.50", "--pack-cap-usd", "5",
            "--archive", str(tmp_path / "runs"), "--packs", str(tmp_path / "packs")]
    assert grid.main(argv) == 2
    assert "12 paid runs × ($0.50 + a judge's $0.00) = $6.00" in capsys.readouterr().out
    assert not (tmp_path / "runs").exists() and not (tmp_path / "packs").exists()
    # a judge's questions are charged to the same cap, at their own bound, in exact arithmetic
    argv[argv.index("5")] = "6.00"
    assert grid.main([*argv, "--judge-model", "gpt-4.1-mini"]) == 2
    assert "= $6.12" in capsys.readouterr().out
    assert not (tmp_path / "runs").exists() and not (tmp_path / "packs").exists()


def test_the_floor_arm_and_the_no_model_provider_come_only_together(tmp_path, capsys):
    from adii.runtime import __main__ as runtime
    for mismatched in (["--provider", "none"], ["--provider", "local", "--model", "m",
                                                "--arm", "always-escalate"]):
        assert runtime.main(["--incident", TWO[0], "--archive", str(tmp_path), *mismatched]) == 2
        assert "floor of the controls asks no model" in capsys.readouterr().out
    assert not any(tmp_path.iterdir())
