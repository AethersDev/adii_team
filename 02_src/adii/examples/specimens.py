"""Six development incidents with scripted example runs — specimens for the inspector.

    python -m adii.examples.specimens            # archive every run into 01_data/runs/
    python -m adii.examples.specimens --csv DIR  # every world as CSV files: the data to bring

What these are. Hand-authored synthetic incidents, one per way an investigation can have
to reason — restore what is missing, remove what is duplicated, fix a wrong relationship,
recognise a legitimate change, admit the evidence cannot settle it, admit the action is not
ADII's to take — plus the ugly endings a real archive will hold: a bound, a rejected repair,
a failed tool, a failed model. They exist so the interface can be designed and tested
against an archive that looks like a product rather than one teaching fixture.

What they are not. The investigator here is a script: it makes its calls and commits its
decision without reading a result, so nothing about a decision below is a claim that it is
correct. No model ran. These carry no evaluation claim, are never eligible for blind
evaluation, and are not the development catalogue proposed in
docs/development_catalog.md — that one is compiled from private material under a decision
record; this one is made up, and says so on every record (`provenance.origin: specimen`,
`configuration.model: null`).

What is real. Every run goes through the real runtime over the real tool layer, so every
observation in every record is what the tools actually returned from the specimen's world,
evidence ids included, and every record is the same run record the runtime writes
for a live run. No mock API, no frontend-only shape.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path

from ..contracts import (
    Disposition,
    IncidentContext,
    InvestigationDecision,
    ToolCall,
    ValidationResult,
)
from ..reporting import RunRecord, write_record
from ..reporting.record import ARCHIVE
from ..runtime.run import Terminated, run_incident
from ..runtime.scripted import EndingInvestigator, ScriptedInvestigator, ScriptedValidator
from ..tools import Parameter, ReadOnlyDatabase, ToolSpec, build_sql_tools

CONFIGURATION = {"provider": "scripted", "model": None, "execution_mode": "scripted",
                 "visibility": "public_development", "blind_evaluation_eligible": False}


@dataclass(frozen=True)
class Run:
    """One scripted trajectory: the calls in order, then how it ends."""
    calls: tuple[ToolCall, ...]
    decision: InvestigationDecision | None = None
    verdict: ValidationResult | None = None
    ending: Terminated | None = None


@dataclass(frozen=True)
class Specimen:
    context: IncidentContext
    world: str                       # SQL that builds the world; opened read-only
    runs: tuple[Run, ...]
    extra_tool: tuple[ToolSpec, object] | None = None   # one specimen registers a failing tool
    # The source of every path the incident permits the investigator to change, by logical
    # id — `transforms/<name>.sql` is served as get_transform("<name>"). A repair target the
    # investigator cannot read would be patched blind; the runtime refuses such an incident.
    transforms: dict[str, str] = field(default_factory=dict)


def sql(name: str, query: str) -> ToolCall:
    return ToolCall(call_id=name, name="run_sql", arguments={"query": query})


def schema(name: str, table: str) -> ToolCall:
    return ToolCall(call_id=name, name="get_schema", arguments={"table": table})


def repair(summary: str, cause: str, repair_id: str, path: str, body: str) -> InvestigationDecision:
    return InvestigationDecision(Disposition.REPAIR, cause, summary, repair_id, {path: body})


def accept(report: str) -> ValidationResult:
    return ValidationResult(True, report, ("pipeline_rebuilds", "row_counts_preserved",
                                           "independent_recomputation"))


def reject(report: str) -> ValidationResult:
    return ValidationResult(False, report, ("pipeline_rebuilds", "row_counts_preserved",
                                            "independent_recomputation"))


def rows(table: str, columns: str, values: list[str]) -> str:
    return f"INSERT INTO {table} ({columns}) VALUES " + ", ".join(values) + ";"


# ── 1. restore what is missing ─────────────────────────────────────────────────────────
ORDERS_MISSING = Specimen(
    IncidentContext("orders-missing-day",
                    "The daily order count for 2026-03-12 is 0. Every other day this month "
                    "is between 118 and 131, and nobody reported an outage.",
                    "2026-03-13T06:00:00Z", ("jobs/load_orders.yml",)),
    "CREATE TABLE orders (order_id TEXT PRIMARY KEY, order_date TEXT NOT NULL, "
    "amount_cents INTEGER);\n"
    + rows("orders", "order_id, order_date, amount_cents", [
        f"('{d}-{n:03d}', '2026-03-{d}', 2500)"
            for d, count in (("10", 124), ("11", 118), ("13", 131), ("14", 127))
        for n in range(1, count + 1)]) + "\n"
    "CREATE TABLE loads (run_date TEXT, status TEXT, rows_loaded INTEGER, note TEXT);\n"
    + rows("loads", "run_date, status, rows_loaded, note", [
        "('2026-03-10', 'SUCCESS', 124, '')", "('2026-03-11', 'SUCCESS', 118, '')",
        "('2026-03-12', 'FAILED', 55, 'source connection reset at row 55; batch rolled back')",
        "('2026-03-13', 'SUCCESS', 131, '')", "('2026-03-14', 'SUCCESS', 127, '')"]),
    (
        Run((schema("c1", "orders"),
             sql("c2", "SELECT order_date, COUNT(*) AS n FROM orders GROUP BY order_date ORDER "
                       "BY order_date"),
             sql("c3", "SELECT run_date, status, rows_loaded, note FROM loads WHERE run_date = "
                       "'2026-03-12'")),
            repair("The load for 2026-03-12 failed at row 55 with a source connection reset and "
                   "was rolled back, so no orders exist for that day. Every other day loaded "
                   "and counts are steady. Re-running the load for that day restores the "
                   "missing rows.",
                   "LOAD_FAILED_AND_ROLLED_BACK", "RERUN_LOAD_2026_03_12",
                   "jobs/load_orders.yml", "rerun:\n  dates: ['2026-03-12']\n  on_conflict: "
                                           "skip\n"),
            accept("Rebuilt from frozen inputs with the rerun applied. 2026-03-12 loads 126 rows; "
                   "no other day changed; independently recomputed daily totals match.")),
        Run((schema("c1", "orders"),
             sql("c2", "SELECT order_date, COUNT(*) AS n FROM orders GROUP BY order_date ORDER "
                       "BY order_date")),
            ending=Terminated("bound_hit", "tool_calls: 2 of 2 used")),
    ),
    transforms={"load_orders": "job: load_orders\nsource: vendor_feed/orders\n"
                               "schedule: daily 05:00\non_failure: rollback_batch\nrerun: []\n"})

# ── 2. recognise a legitimate change ───────────────────────────────────────────────────
REVENUE_AFTER_DEPLOY = Specimen(
    IncidentContext("revenue-after-deploy",
                    "Daily revenue is down about 45% since 2026-03-08, the day release v2.3.1 "
                    "was deployed. Product wants the release rolled back.",
                    "2026-03-11T09:00:00Z", ("transforms/revenue_daily.sql",)),
    "CREATE TABLE revenue_daily (day TEXT PRIMARY KEY, distributor TEXT, revenue_usd REAL);\n"
    + rows("revenue_daily", "day, distributor, revenue_usd", [
        "('2026-03-06', 'all', 41200.0)", "('2026-03-07', 'all', 40850.0)",
        "('2026-03-08', 'all', 22600.0)", "('2026-03-09', 'all', 22900.0)", "('2026-03-10', "
                                                                            "'all', 22300.0)"])
    + "\nCREATE TABLE distributors (name TEXT, contract_end TEXT, share_of_revenue REAL);\n"
    + rows("distributors", "name, contract_end, share_of_revenue", [
        "('Northwind', '2026-03-07', 0.27)", "('Harbor', '2026-03-07', 0.18)",
        "('Meridian', NULL, 0.31)", "('Direct', NULL, 0.24)"])
    + "\nCREATE TABLE deploys (deployed_at TEXT, release TEXT, touches TEXT);\n"
    + rows("deploys", "deployed_at, release, touches", [
        "('2026-03-08T02:10:00Z', 'v2.3.1', 'checkout UI copy; no pricing or pipeline change')"]),
    (
        Run((sql("c1", "SELECT day, revenue_usd FROM revenue_daily ORDER BY day"),
             sql("c2", "SELECT name, contract_end, share_of_revenue FROM distributors WHERE "
                       "contract_end IS NOT NULL"),
             sql("c3", "SELECT deployed_at, release, touches FROM deploys")),
            InvestigationDecision(Disposition.NO_REPAIR, "DISTRIBUTOR_CONTRACTS_ENDED",
                                  "Two distributors, Northwind and Harbor, ended their "
                                  "contracts on "
                                  "2026-03-07; together they carried 45% of revenue. The release "
                                  "deployed the next morning touched checkout copy only. The "
                                  "pipeline "
                                  "is reporting a real decline correctly; nothing to repair.")),
    ),
    transforms={"revenue_daily": "-- revenue_daily: total revenue per day, in USD, across every "
                                 "distributor.\n-- Source amounts are already in USD; no unit "
                                 "conversion happens here.\nSELECT order_day AS day, 'all' AS "
                                 "distributor, SUM(amount_usd) AS revenue_usd\nFROM fct_orders\n"
                                 "GROUP BY order_day;\n"})

# ── 3. remove what is duplicated ───────────────────────────────────────────────────────
DELIVERY_DUPLICATED = Specimen(
    IncidentContext("delivery-duplicated",
                    "Deliveries reported for 2026-03-11 are exactly double the shipments "
                    "dispatched that day. The carrier confirms it delivered each parcel once.",
                    "2026-03-12T07:30:00Z", ("transforms/stg_deliveries.sql",)),
    "CREATE TABLE shipments (shipment_id TEXT PRIMARY KEY, ship_date TEXT);\n"
    + rows("shipments", "shipment_id, ship_date",
           [f"('S{n:03d}', '2026-03-11')" for n in range(1, 41)])
    + "\nCREATE TABLE deliveries (shipment_id TEXT, delivered_at TEXT, batch TEXT);\n"
    + rows("deliveries", "shipment_id, delivered_at, batch", [
        f"('S{n:03d}', '2026-03-11T18:{n % 60:02d}:00Z', 'B-771')" for n in range(1, 41)] + [
        f"('S{n:03d}', '2026-03-11T18:{n % 60:02d}:00Z', 'B-771-retry')" for n in range(1, 41)])
    + "\nCREATE TABLE delivery_log (batch TEXT, event TEXT, at TEXT);\n"
    + rows("delivery_log", "batch, event, at", [
        "('B-771', 'received', '2026-03-11T19:00:04Z')", "('B-771', 'ack timeout', "
                                                         "'2026-03-11T19:00:34Z')",
        "('B-771-retry', 'received', '2026-03-11T19:00:41Z')"]),
    (
        Run((sql("c1", "SELECT COUNT(*) AS shipped FROM shipments WHERE ship_date = '2026-03-11'"),
             sql("c2", "SELECT batch, COUNT(*) AS n FROM deliveries GROUP BY batch"),
             sql("c3", "SELECT batch, event, at FROM delivery_log ORDER BY at")),
            repair("Batch B-771 was received, its acknowledgement timed out, and the carrier "
                   "replayed it as B-771-retry: every shipment appears twice. Dropping the "
                   "retry batch "
                   "removes the duplicates.",
                   "DELIVERY_BATCH_REPLAYED", "DROP_RETRY_BATCH",
                   "transforms/stg_deliveries.sql", "SELECT * FROM deliveries WHERE batch NOT "
                                                    "LIKE '%-retry';\n"),
            reject("Rebuilt from frozen inputs with the patch applied. The retry batch is "
                   "dropped for "
                   "every day, not only 2026-03-11: 2026-03-04 has a legitimate retry-only "
                   "batch and "
                   "loses 12 deliveries. Row counts for that day do not match the independent "
                   "recomputation.")),
        Run((sql("c1", "SELECT COUNT(*) AS shipped FROM shipments WHERE ship_date = '2026-03-11'"),
             sql("c2", "SELECT batch, COUNT(*) AS n FROM deliveries GROUP BY batch"),
             sql("c3", "SELECT batch, event, at FROM delivery_log ORDER BY at")),
            repair("Batch B-771 was received, its acknowledgement timed out, and the carrier "
                   "replayed it as B-771-retry: every shipment of 2026-03-11 appears twice. "
                   "Keeping "
                   "one delivery per shipment, the earliest, removes the duplicates without "
                   "touching "
                   "days where a retry was the only delivery.",
                   "DELIVERY_BATCH_REPLAYED", "DEDUPE_ONE_PER_SHIPMENT",
                   "transforms/stg_deliveries.sql",
                   "SELECT shipment_id, MIN(delivered_at) AS delivered_at FROM deliveries GROUP "
                   "BY shipment_id;\n"),
            accept("Rebuilt from frozen inputs with the patch applied. 2026-03-11 reports 40 "
                   "deliveries "
                   "against 40 shipments; every other day unchanged; independently recomputed.")),
    ),
    transforms={"stg_deliveries": "-- stg_deliveries: every delivery event the carrier sent, as "
                                  "received.\nSELECT shipment_id, delivered_at, batch\n"
                                  "FROM deliveries;\n"})

# ── 4. the evidence cannot settle it ───────────────────────────────────────────────────
SHIPMENT_COUNTS = Specimen(
    IncidentContext("shipment-counts-disagree",
                    "The warehouse system says 25 parcels shipped on 2026-03-10. The carrier's "
                    "manifest lists 18. Finance needs to know which number to bill.",
                    "2026-03-11T10:00:00Z", ()),
    "CREATE TABLE warehouse_shipments (parcel_id TEXT PRIMARY KEY, ship_date TEXT);\n"
    + rows("warehouse_shipments", "parcel_id, ship_date",
           [f"('P{n:02d}', '2026-03-10')" for n in range(1, 26)])
    + "\nCREATE TABLE carrier_manifest (parcel_id TEXT PRIMARY KEY, scanned_at TEXT);\n"
    + rows("carrier_manifest", "parcel_id, scanned_at", [f"('P{n:02d}', "
                                                          "'2026-03-10T16:{n:02d}:00Z')"
                                                              for n in range(1, 19)]),
    (
        Run((sql("c1", "SELECT COUNT(*) AS n FROM warehouse_shipments WHERE ship_date = "
                       "'2026-03-10'"),
             sql("c2", "SELECT COUNT(*) AS n FROM carrier_manifest"),
             sql("c3", "SELECT parcel_id FROM warehouse_shipments WHERE parcel_id NOT IN "
                       "(SELECT parcel_id FROM carrier_manifest)"),
             sql("c4", "SELECT * FROM dock_export_receipts WHERE export_date = '2026-03-10'")),
            InvestigationDecision(Disposition.ESCALATE, None,
                                  "Seven parcels, P19 to P25, were recorded as shipped by the "
                                  "warehouse "
                                  "and never scanned by the carrier. Whether they left the dock "
                                  "is the "
                                  "decisive fact, and no export receipt exists to settle it: "
                                  "the receipts "
                                  "table is not in this warehouse. Neither number can be billed "
                                  "on this "
                                  "evidence; someone with access to the dock records has to "
                                  "decide.")),
    ))

# ── 5. the action is not ADII's to take ────────────────────────────────────────────────
SETTLEMENT_CONFLICT = Specimen(
    IncidentContext("settlement-conflict",
                    "The card processor's settlement for 2026-03-09 is 4,120.00 lower than the "
                    "ledger. The ledger is the book of record; the processor's file is signed.",
                    "2026-03-10T11:00:00Z", ()),
    "CREATE TABLE ledger (day TEXT PRIMARY KEY, settled_usd REAL);\n"
    + rows("ledger", "day, settled_usd", ["('2026-03-08', 88120.0)", "('2026-03-09', 91340.0)"])
    + "\nCREATE TABLE processor_settlements (day TEXT PRIMARY KEY, settled_usd REAL, "
      "file_signature TEXT);\n"
    + rows("processor_settlements", "day, settled_usd, file_signature", [
        "('2026-03-08', 88120.0, 'sig:9c1f')", "('2026-03-09', 87220.0, 'sig:4be0')"])
    + "\nCREATE TABLE ledger_adjustments (day TEXT, amount_usd REAL, approved_by TEXT);\n",
    (
        Run((sql("c1", "SELECT l.day, l.settled_usd AS ledger, p.settled_usd AS processor FROM "
                       "ledger l JOIN processor_settlements p ON l.day = p.day"),
             sql("c2", "SELECT * FROM ledger_adjustments WHERE day = '2026-03-09'")),
            InvestigationDecision(Disposition.ESCALATE, "SETTLEMENT_MISMATCH_UNADJUSTED",
                                  "The ledger and the signed processor file disagree by "
                                  "4,120.00 for "
                                  "2026-03-09 and no adjustment has been approved. Changing either "
                                  "figure is a finance decision under signature; ADII holds no "
                                  "write "
                                  "path here and would not use one if it did.")),
        Run((sql("c1", "SELECT l.day, l.settled_usd AS ledger, p.settled_usd AS processor FROM "
                       "ledger l JOIN processor_settlements p ON l.day = p.day"),),
            ending=Terminated("model_failure", "the provider returned an empty message on three "
                                               "attempts")),
    ))

# ── 6. a relationship is wrong ─────────────────────────────────────────────────────────
REGION_HISTORY = ToolSpec("region_history", "The history of region assignments for one customer.",
                          (Parameter("customer_id", "string", "The customer to look up."),))


def region_history_unavailable(customer_id: str) -> dict[str, object]:
    raise RuntimeError("the region history service is not reachable from this warehouse")


REGION_MISASSIGNED = Specimen(
    IncidentContext("customer-region-misassigned",
                    "Since 2026-03-09, EU revenue is up 30% and US revenue is down 30% while the "
                    "total is unchanged. No campaign or pricing change is known in either region.",
                    "2026-03-11T08:00:00Z", ("transforms/dim_customer.sql",)),
    "CREATE TABLE customers (customer_id TEXT PRIMARY KEY, country TEXT);\n"
    + rows("customers", "customer_id, country", [
        "('C1', 'US')", "('C2', 'US')", "('C3', 'DE')", "('C4', 'FR')", "('C5', 'US')", "('C6', "
                                                                                        "'NL')"])
    + "\nCREATE TABLE region_map (country TEXT PRIMARY KEY, region TEXT, valid_from TEXT);\n"
    + rows("region_map", "country, region, valid_from", [
        "('DE', 'EU', '2025-01-01')", "('FR', 'EU', '2025-01-01')", "('NL', 'EU', '2025-01-01')",
        "('US', 'EU', '2026-03-09')"])
    + "\nCREATE TABLE revenue_by_region (day TEXT, region TEXT, revenue_usd REAL);\n"
    + rows("revenue_by_region", "day, region, revenue_usd", [
        "('2026-03-08', 'US', 30000.0)", "('2026-03-08', 'EU', 30000.0)",
        "('2026-03-09', 'US', 21000.0)", "('2026-03-09', 'EU', 39000.0)"]),
    (
        Run((sql("c1", "SELECT day, region, revenue_usd FROM revenue_by_region ORDER BY day, "
                       "region"),
             sql("c2", "SELECT country, region, valid_from FROM region_map ORDER BY valid_from "
                       "DESC")),
            repair("The region map assigns US to EU from 2026-03-09. Every US customer's revenue "
                   "has been counted as EU since that day, which moves 30% of revenue between the "
                   "regions and leaves the total unchanged. Restoring US to the US region fixes "
                   "the "
                   "assignment.",
                   "REGION_MAP_WRONG_ASSIGNMENT", "RESTORE_US_REGION",
                   "transforms/dim_customer.sql",
                   "UPDATE region_map SET region = 'US' WHERE country = 'US' AND valid_from = "
                   "'2026-03-09';\n"),
            accept("Rebuilt from frozen inputs with the patch applied. Regional revenue for "
                   "2026-03-09 "
                   "independently recomputed as 30,000 US / 30,000 EU; totals unchanged; row "
                   "counts preserved.")),
        Run((sql("c1", "SELECT day, region, revenue_usd FROM revenue_by_region ORDER BY day, "
                       "region"),
             ToolCall("c2", "region_history", {"customer_id": "C1"})),
            InvestigationDecision(Disposition.ESCALATE, None,
                                  "Revenue moved from US to EU on 2026-03-09 with the total "
                                  "unchanged, "
                                  "which points at a region assignment. The region history service "
                                  "failed when asked, so whether the assignment changed on purpose "
                                  "cannot be established from here.")),
    ),
    extra_tool=(REGION_HISTORY, region_history_unavailable),
    transforms={"dim_customer": "-- dim_customer: each customer with the region its country maps "
                                "to.\nSELECT c.customer_id, c.country, m.region\nFROM customers c\n"
                                "JOIN region_map m ON m.country = c.country;\n"})

SPECIMENS = (ORDERS_MISSING, REVENUE_AFTER_DEPLOY, DELIVERY_DUPLICATED, SHIPMENT_COUNTS,
             SETTLEMENT_CONFLICT, REGION_MISASSIGNED)


def produce(specimen: Specimen, index: int, run: Run) -> RunRecord:
    """One run of one specimen through the real runtime over the real tool layer."""
    tools = build_sql_tools(ReadOnlyDatabase.in_memory(specimen.world),
                            transform_sources=specimen.transforms or None)
    if specimen.extra_tool:
        tools.register(*specimen.extra_tool)
    investigator = (EndingInvestigator(run.calls, run.ending) if run.ending
                    else ScriptedInvestigator(run.calls, run.decision))
    return run_incident(f"{specimen.context.incident_id}-run-{index}", specimen.context,
                        investigator, tools, ScriptedValidator(run.verdict),
                        configuration={**CONFIGURATION, "tools": list(tools.names)})


def records() -> list[RunRecord]:
    return [produce(s, i, run) for s in SPECIMENS for i, run in enumerate(s.runs, start=1)]


def write_csv(root: Path) -> list[Path]:
    """Every specimen's world as CSV files, `root/<incident>/<table>.csv`, with the alert
    beside them in `alert.txt`: the data to bring to the page's own form, so the product
    path can be rehearsed on a world whose answer is known. Read back through the tool
    layer's world builder (tools/user_world.py), each file becomes the same table again."""
    written = []
    for specimen in SPECIMENS:
        folder = root / specimen.context.incident_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "alert.txt").write_text(specimen.context.alert + "\n", encoding="utf-8",
                                          newline="\n")
        world = ReadOnlyDatabase.in_memory(specimen.world)
        for table in world.tables():
            result = world.query(f'SELECT * FROM "{table}"', max_rows=100_000)
            path = folder / f"{table}.csv"
            # LF, not csv's default CRLF: the repository stores every text file as LF
            # (.gitattributes), and the committed folder is held to these bytes exactly.
            with path.open("w", encoding="utf-8", newline="") as sink:
                writer = csv.writer(sink, lineterminator="\n")
                writer.writerow(result.columns)
                writer.writerows([["" if v is None else v for v in row] for row in result.rows])
            written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--archive", default=str(ARCHIVE), metavar="DIR",
                        help="archive root (default: 01_data/runs); a taken label is skipped")
    parser.add_argument("--csv", metavar="DIR",
                        help="write every specimen's world as CSV files under DIR instead")
    args = parser.parse_args(argv)
    if args.csv:
        for path in write_csv(Path(args.csv)):
            print(f"wrote {path}")
        return 0
    written = skipped = 0
    for record in records():
        try:
            print(f"archived {write_record(record, Path(args.archive))}")
            written += 1
        except FileExistsError:
            skipped += 1
    print(f"{written} archived, {skipped} already there. Development specimens: scripted, no "
           "model, "
          "no evaluation claim.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
