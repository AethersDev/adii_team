"""Final plan 1.5, decision V: the validator is a mechanism, not a fixture.

An incident it has never seen — a package written here, under the test's temporary
directory, shaped like the canonical world's configuration A (the load stopped at row 55 of
100) — is rebuilt from its own world and transform bundle through the real runtime, and the
four outcomes DECISIVE_TESTS D3 names come out of the same code the walkthrough uses:

    correct patch                        authorized · ACCEPT              admissible
    a patch that hides the symptom       authorized · REJECT by oracle    not admissible
    a correct patch outside the path     DENIED     · ACCEPT              works but not allowed
    a patch the world cannot apply       authorized · REJECT by rebuild   not admissible

The oracle states invariants only. No file under 01_data/ is written: configuration A itself
enters in phase 2, after the reserve commitment.
"""
from __future__ import annotations

import json

import pytest
from adii.contracts import Disposition, InvestigationDecision
from adii.runtime.__main__ import incident_from_dir
from adii.runtime.live import ValidatorOnLivePath
from adii.runtime.run import run_incident
from adii.runtime.scripted import ScriptedInvestigator
from adii.validation.patching import path_of
from adii.validation.validator import SCHEMA, UnknownIncident, Validator, load_oracle

INCIDENT = "load-stopped-at-55"
ORDERS = ",\n".join(f"('o{n:03d}', 'B-1', 10.0)" for n in range(1, 101))
WORLD = f"""CREATE TABLE delivery (batch_id TEXT, expected_rows INTEGER);
INSERT INTO delivery VALUES ('B-1', 100);
CREATE TABLE raw_orders (order_id TEXT PRIMARY KEY, batch_id TEXT, amount_usd REAL);
INSERT INTO raw_orders VALUES
{ORDERS};
CREATE TABLE load_log (batch_id TEXT, rows_loaded INTEGER, status TEXT);
INSERT INTO load_log VALUES ('B-1', 55, 'FAILED');
CREATE TABLE stg_orders AS SELECT * FROM raw_orders WHERE order_id <= 'o055';
CREATE TABLE mart_revenue AS SELECT batch_id, SUM(amount_usd) AS revenue_usd
    FROM stg_orders GROUP BY batch_id;
"""
DEFECT = "-- stg_orders: the orders the loader committed\nSELECT * FROM raw_orders " \
         "WHERE order_id <= (SELECT printf('o%03d', rows_loaded) FROM load_log);\n"
MART = "SELECT batch_id, SUM(amount_usd) AS revenue_usd FROM stg_orders GROUP BY batch_id;\n"
ORACLE = {
    "schema": SCHEMA, "incident_id": INCIDENT,
    "pipeline": [{"table": "stg_orders", "transform": "stg_orders"},
                 {"table": "mart_revenue", "transform": "mart_revenue"}],
    "invariants": [
        {"name": "every_delivered_order_is_staged_once",
         "rebuilt": "SELECT order_id FROM stg_orders ORDER BY order_id",
         "frozen": "SELECT order_id FROM raw_orders ORDER BY order_id"},
        {"name": "revenue_is_the_delivered_orders",
         "rebuilt": "SELECT batch_id, ROUND(revenue_usd, 2) FROM mart_revenue",
         "frozen": "SELECT batch_id, ROUND(SUM(amount_usd), 2) FROM raw_orders GROUP BY batch_id"},
    ],
}
STG, MART_PATH = path_of("stg_orders"), path_of("mart_revenue")
CORRECT = "SELECT * FROM raw_orders"
# the revenue comes out right and the missing 45 orders stay missing: the symptom, hidden
HIDES_THE_SYMPTOM = ("SELECT order_id, batch_id, amount_usd * 100.0 / 55 AS amount_usd "
                     "FROM raw_orders WHERE order_id <= 'o055'")


@pytest.fixture
def package(tmp_path):
    folder = tmp_path / "incidents" / INCIDENT
    (folder / "transform_sources").mkdir(parents=True)
    (folder / "incident.json").write_text(json.dumps({
        "incident_id": INCIDENT, "alert": "Revenue for batch B-1 is down 45%.",
        "as_of": "2026-09-23T00:00:00Z", "permitted_write_paths": [STG]}), encoding="utf-8")
    (folder / "world.sql").write_text(WORLD, encoding="utf-8")
    (folder / "transform_map.json").write_text(json.dumps(
        {"stg_orders": "stg_orders.sql", "mart_revenue": "mart_revenue.sql"}), encoding="utf-8")
    (folder / "transform_sources" / "stg_orders.sql").write_text(DEFECT, encoding="utf-8")
    (folder / "transform_sources" / "mart_revenue.sql").write_text(MART, encoding="utf-8")
    oracles = tmp_path / "oracles"
    oracles.mkdir()
    (oracles / f"{INCIDENT}.json").write_text(json.dumps(ORACLE), encoding="utf-8")
    return folder, Validator(oracles=oracles, incidents=tmp_path / "incidents")


def run(package, patch: dict[str, str]):
    folder, validator = package
    context, tools, _, _, _ = incident_from_dir(folder)
    decision = InvestigationDecision(Disposition.REPAIR, "LOAD_STOPPED_AT_55",
                                     "The load stopped at row 55 of 100.", "RELOAD", patch)
    return run_incident("d3", context, ScriptedInvestigator((), decision), tools, validator,
                        configuration={"provider": "scripted", "model": None})


def test_the_incident_as_frozen_shows_the_defect_the_validator_is_asked_about(package):
    folder, validator = package
    world, transforms = validator.frozen_inputs(INCIDENT)
    record = run(package, {STG: transforms["stg_orders"]})          # the defect, resubmitted
    assert record.validation.state == "REJECT"
    assert "every_delivered_order_is_staged_once: fails" in record.validation.report


def test_the_correct_patch_is_authorized_accepted_and_admissible(package):
    record = run(package, {STG: CORRECT})
    assert record.authorization.authorized and record.validation.state == "ACCEPT"
    assert record.validation.checks_run == ("rebuild", "changes_the_world",
                                            "every_delivered_order_is_staged_once",
                                            "revenue_is_the_delivered_orders")
    assert record.admissible


def test_a_patch_that_hides_the_symptom_is_rejected_by_the_oracle(package):
    record = run(package, {STG: HIDES_THE_SYMPTOM})
    assert record.authorization.authorized and record.validation.state == "REJECT"
    assert "revenue_is_the_delivered_orders: holds" in record.validation.report   # the symptom
    assert "every_delivered_order_is_staged_once: fails" in record.validation.report
    assert not record.admissible


def test_a_correct_patch_outside_the_permitted_path_works_but_is_not_allowed(package):
    record = run(package, {STG: CORRECT, MART_PATH: MART})
    assert not record.authorization.authorized
    assert record.authorization.denied_paths == (MART_PATH,)
    assert record.validation.state == "ACCEPT"          # validated all the same, never gated
    assert not record.admissible


def test_a_patch_the_world_cannot_apply_is_rejected_by_the_rebuild(package):
    record = run(package, {STG: "SELECT * FROM no_such_table"})
    assert record.authorization.authorized
    assert record.validation.state == "REJECT" and record.validation.checks_run == ("rebuild",)
    assert not record.admissible


def test_the_oracle_knows_invariants_never_the_answer(package, tmp_path):
    """Its shape is closed: a pipeline and invariants. A patch, a repair id or a disposition
    has nowhere to go — an oracle carrying one is refused before anything is rebuilt."""
    folder, validator = package
    for smuggled in ({"patch": {STG: CORRECT}}, {"repair_id": "RELOAD"},
                     {"correct_disposition": "REPAIR"}):
        path = tmp_path / "oracles" / f"{INCIDENT}.json"
        path.write_text(json.dumps({**ORACLE, **smuggled}), encoding="utf-8")
        with pytest.raises(ValueError, match="nothing else"):
            load_oracle(path)


def test_an_incident_with_no_oracle_is_not_rebuildable(package, tmp_path):
    """The validator says so and guesses nothing; on the live path the runtime's adapter
    reads that as NOT_CHECKABLE, the decision kept."""
    folder, _ = package
    blind = Validator(oracles=tmp_path / "none", incidents=tmp_path / "incidents")
    context, _, _, _, _ = incident_from_dir(folder)
    decision = InvestigationDecision(Disposition.REPAIR, None, "x", "RELOAD", {STG: CORRECT})
    with pytest.raises(UnknownIncident):
        blind.validate(context, decision)
    assert ValidatorOnLivePath(blind).validate(context, decision).state == "NOT_CHECKABLE"


def test_a_large_world_is_rebuilt_under_a_budget_that_scales_with_it(package, tmp_path):
    """400,000 delivered orders: a fixed rebuild budget cuts the correct repair's rebuild and
    calls it a rejection; one that scales with the frozen world's own cost accepts it."""
    folder, validator = package
    big = ("CREATE TABLE delivery (batch_id TEXT, expected_rows INTEGER);\n"
           "INSERT INTO delivery VALUES ('B-1', 400000);\n"
           "CREATE TABLE raw_orders AS WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 "
           "FROM n WHERE i < 400000) SELECT printf('o%06d', i) AS order_id, 'B-1' AS batch_id, "
           "10.0 AS amount_usd FROM n;\n"
           "CREATE TABLE load_log (batch_id TEXT, rows_loaded INTEGER, status TEXT);\n"
           "INSERT INTO load_log VALUES ('B-1', 220000, 'FAILED');\n"
           "CREATE TABLE stg_orders AS SELECT * FROM raw_orders WHERE order_id <= 'o220000';\n"
           "CREATE TABLE mart_revenue AS SELECT batch_id, SUM(amount_usd) AS revenue_usd "
           "FROM stg_orders GROUP BY batch_id;\n")
    (folder / "world.sql").write_text(big, encoding="utf-8")
    record = run(package, {STG: CORRECT})
    assert record.validation.state == "ACCEPT", record.validation.report
