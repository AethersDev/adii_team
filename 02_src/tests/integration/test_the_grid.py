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
    assert "Runs not scored: none" in (tmp_path / "packs" / "t.report.md").read_text(
        encoding="utf-8")
    # requirement D5: a run with no evaluation report is named unscored, never by how it ended
    first = tmp_path / "runs" / runs[0]
    (first / "evaluation_report.json").unlink()
    assert grid.main(["--pack", "t", "--report", "--archive", str(tmp_path / "runs"),
                      "--packs", str(tmp_path / "packs")]) == 0
    result = json.loads((tmp_path / "packs" / "t.report.json").read_text(encoding="utf-8"))
    assert result["unscored"] == [runs[0]]
    assert next(r for r in result["runs"] if r["label"] == runs[0])["category"] == "unscored"
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


def test_a_reasoning_effort_is_a_pack_term_that_reaches_every_paid_cell(tmp_path, monkeypatch,
                                                                         capsys):
    pack = {"pack": "p", "provider": "openai", "model": "gpt-6-sol", "max_turns": 20,
            "max_cost_usd": 0.5, "max_tokens": 4096, "reasoning_effort": "low"}
    asked = []
    monkeypatch.setattr(grid.runtime, "main", lambda argv: asked.append(argv) or 0)
    grid.run_cell(pack, "p-x-full-r1", TWO[0], "full", tmp_path)
    grid.run_cell({k: v for k, v in pack.items() if k != "reasoning_effort"}, "p-x-full-r2",
                  TWO[0], "full", tmp_path)
    assert asked[0][-2:] == ["--reasoning-effort", "low"]
    assert "--reasoning-effort" not in asked[1]
    assert grid.main(["--pack", "q", "--provider", "local", "--model", "m",
                      "--reasoning-effort", "low", "--packs", str(tmp_path / "packs")]) == 2
    assert "--provider openai" in capsys.readouterr().out
    assert not (tmp_path / "packs").exists()


def test_a_local_models_weights_are_a_term_its_pack_resumes_only_with(tmp_path, endpoint,
                                                                       capsys):
    """A local subject is named by its bytes: a hidden file is not the model, and a pack begun
    on one set of weights is refused on any other — a registered one, on any but the frozen."""
    weights = tmp_path / "model"
    (weights / ".cache").mkdir(parents=True)
    (weights / "model.safetensors").write_bytes(b"weights")
    (weights / ".cache" / "download").write_text("a", encoding="utf-8")
    FakeModel.script[:] = [END] * 4
    assert grid.main(args(tmp_path, endpoint, "--arms", "full", "--weights", str(weights))) == 0
    receipt = json.loads((tmp_path / "packs" / "t.json").read_text(encoding="utf-8"))
    assert receipt["weights_sha256"] == grid.weights_digest(weights)
    (weights / ".cache" / "download").write_text("b", encoding="utf-8")
    assert grid.weights_digest(weights) == receipt["weights_sha256"]
    (weights / "model.safetensors").write_bytes(b"other weights")
    assert grid.main(args(tmp_path, endpoint, "--arms", "full", "--weights", str(weights))) == 2
    assert "resumes only as it began" in capsys.readouterr().out


def test_a_local_pack_sends_and_records_its_completion_bound(tmp_path, endpoint):
    """Unsent, a local server's own default binds instead — mlx-lm's is 512 — and no receipt
    says so: the pack's bound reaches the endpoint and every run's receipt."""
    FakeModel.script[:] = [END] * 4
    assert grid.main(args(tmp_path, endpoint, "--arms", "full", "--max-tokens", "4096")) == 0
    assert {body.get("max_completion_tokens") for body in FakeModel.seen} == {4096}
    for run in (tmp_path / "runs").iterdir():
        told = json.loads((run / "receipt.json").read_text(encoding="utf-8"))
        assert told["configuration"]["max_tokens"] == 4096


def test_a_pack_runs_its_registered_partition_and_the_benchmark_by_default(tmp_path,
                                                                          monkeypatch):
    """Decision E: which incidents a pack runs is registered before any final run
    (catalogue/partition.json); the default is the benchmark, which holds no burned case."""
    monkeypatch.setattr(grid, "run_cell", lambda *a: 0)
    for partition, argv in (("benchmark", []), ("held_out", ["--partition", "held_out"])):
        grid.main(["--pack", partition, "--provider", "local", "--model", "m", "--repeats", "1",
                   "--arms", "always-escalate", *argv, "--archive", str(tmp_path / "runs"),
                   "--packs", str(tmp_path / "packs")])
        promised = json.loads((tmp_path / "packs" / f"{partition}.json").read_text(
            encoding="utf-8"))
        assert promised["incidents"] == grid.PARTITION[partition]
    assert len(grid.PARTITION["benchmark"]) == 12
    assert not grid.BURNED & set(grid.PARTITION["benchmark"])
