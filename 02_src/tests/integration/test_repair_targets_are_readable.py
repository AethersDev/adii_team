"""A permitted write path is a repair target, and a repair target the investigator cannot
read would be patched blind — three paid runs asked to read the one file they were told they
could change and were refused, and one then rewrote it unseen. So the rule is a system
property, held here over every incident the runtime can load and at the runtime's door:
`transforms/<name>.sql` is served by `get_transform("<name>")`, and an incident that permits
a path it cannot show is refused before any label."""
from __future__ import annotations

import json
from pathlib import PurePosixPath

import pytest
from adii.contracts import ToolCall
from adii.examples.specimens import SPECIMENS
from adii.examples.walkthrough import FIXTURE, load
from adii.runtime import __main__ as cli
from adii.runtime.__main__ import incident, readable_or_refused
from adii.validation.patching import apply_patch, path_of
from adii.validation.validator import ORACLES, Validator, load_oracle

TRANSFORM = path_of("stg_orders")

INCIDENTS = [load()[0].incident_id, *(s.context.incident_id for s in SPECIMENS)]


def served(tools, path: str) -> dict:
    """Read the permitted path through the evidence surface, as a model would."""
    result = tools.execute(ToolCall(call_id="t", name="get_transform",
                                    arguments={"transform_id": PurePosixPath(path).stem}))
    assert result.status == "OK", (path, result.content)
    return result.content


@pytest.mark.parametrize("incident_id", INCIDENTS)
def test_every_permitted_repair_target_is_readable_through_the_evidence_surface(incident_id):
    context, tools, _, _, evidence = incident(incident_id)
    for path in context.permitted_write_paths:
        content = served(tools, path)
        assert content["source"].strip() and content["truncated"] is False
    if context.permitted_write_paths:
        assert "transforms" in evidence, "the receipt names what the model may read"
    else:
        assert "get_transform" not in tools.names   # nothing to read, nothing advertised


def test_the_walkthroughs_served_transform_is_the_defect_and_the_committed_patch_removes_it():
    """The file the investigator reads is the one before the repair: applied as-is it
    reproduces the incident (revenue a hundredth of the order count); the patch committed
    with the fixture is the correction to exactly that file."""
    context, tools, _, _, _ = incident("demo-learning-001")
    source = served(tools, TRANSFORM)["source"]
    assert "/ 100.0 / 100.0" in source
    pipeline, _ = load_oracle(ORACLES / "demo-learning-001.json")
    world, transforms = Validator().frozen_inputs("demo-learning-001")
    broken = apply_patch(world, pipeline, transforms, {TRANSFORM: source})
    day, revenue = broken.query("SELECT day, revenue_usd FROM mart_daily ORDER BY day",
                                max_rows=1).rows[0]
    orders = broken.query("SELECT count(*) FROM orders WHERE order_date = ?", max_rows=1,
                          parameters=(day,)).rows[0][0]
    assert revenue == pytest.approx(orders / 100)
    patch = json.loads((FIXTURE / "decision.json").read_text(encoding="utf-8"))["patch"]
    assert set(patch) == {TRANSFORM} and patch[TRANSFORM] != source


def test_an_incident_that_permits_a_path_it_cannot_show_is_refused_before_any_label(tmp_path,
                                                                                    capsys):
    brought = tmp_path / "brought"
    brought.mkdir()
    (brought / "incident.json").write_text(json.dumps({
        "incident_id": "blind-1", "alert": "x", "as_of": "2026-09-22",
        "permitted_write_paths": ["transforms/revenue_daily.sql"]}), encoding="utf-8")
    (brought / "world.sql").write_text("CREATE TABLE revenue (day TEXT);", encoding="utf-8")
    archive = tmp_path / "runs"
    assert cli.main(["--incident-dir", str(brought), "--provider", "local",
                     "--endpoint", "http://127.0.0.1:9", "--model", "m",
                     "--archive", str(archive)]) == 2
    out = capsys.readouterr().out
    assert "transforms/revenue_daily.sql" in out and "patched blind" in out
    assert not archive.exists() or not any(archive.iterdir())


def test_the_rule_is_by_stem_and_passes_only_when_every_path_is_served():
    from adii.contracts import IncidentContext
    context = IncidentContext("i", "a", "t", ("transforms/a.sql", "jobs/b.yml"))
    readable_or_refused(context, {"a": "SELECT 1", "b": "job: b"})
    with pytest.raises(ValueError, match="jobs/b.yml"):
        readable_or_refused(context, {"a": "SELECT 1"})
    readable_or_refused(IncidentContext("i", "a", "t", ()), {})
