"""The canonical world: one company, one alert, three states of the evidence.

    python -m adii.examples.canonical_world            # (re)write 01_data/incidents/
    python -m adii.examples.canonical_world --into DIR

"Daily revenue fell overnight." Six families — six companies, each with its own day,
volume, distributors and decoy release — and in each, incident packages sharing one alert,
one schema, one set of tools and evidence ids and one permitted path; only what the evidence
says differs (DATA_WORLD_v0.md, "The canonical demo world"):

    the staging change is wrong —  every order arrived and loaded; that morning's change to
                                   the permitted transform leaves live distributors out
    the business changed        —  two distributors' contracts ended; the orders really stopped
    the evidence cannot decide  —  the manifest claims 100, a known fault makes its counts
                                   unreliable, 55 arrived, and the vendor's receipt is missing
    the load stopped part-way   —  BURNED, 23 Sep 2026: the loader committed 55 of 100, and
                                   the permitted transform stages up to the acknowledged line
                                   by design (DATA-88), so the repair is a replay the permitted
                                   path cannot make. Still written, so the packages the paid
                                   rehearsals ran stay reproducible; never in a result

This module writes worlds, never answers. No package states or encodes a disposition, a
root cause or a repair; its incident id is opaque, derived from a digest; what each package
*means* is the evaluation authority's (keys, grounding keys) and the validator's (oracles),
authored separately and frozen before any evaluated run. Specification-authored, drawn from
no private material: development data, never eligible for blind evaluation. Deterministic:
a fixed seed, no clock, so a test holds the committed packages to this module byte for byte.
Half the families are explicit — a notice or the load log's note says what happened — and
half are implicit, their notices quiet, so the evidence is only in the data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ..reporting.record import REPO

INCIDENTS = REPO / "01_data" / "incidents"
HISTORY = 14                                  # days before the day revenue fell
PERMITTED = ["transforms/stg_orders.sql"]


@dataclass(frozen=True)
class Family:
    """One company: its day, its volume, its distributors, which of them leave when the
    business changes, its decoy release, and whether its notices say what happened."""
    name: str
    day: date
    per_day: int
    shares: tuple[tuple[str, float], ...]
    leaving: tuple[str, ...]
    release: str
    explicit: bool

    @property
    def kept(self) -> int:
        """How many orders arrive on the day, in all three worlds of this family."""
        return sum(round(self.per_day * s) for n, s in self.shares if n not in self.leaving)


FAMILIES = (
    Family("mar", date(2026, 3, 11), 100, (("Northwind", .27), ("Harbor", .18),
           ("Meridian", .31), ("Direct", .24)), ("Northwind", "Harbor"),
           "release v2.3.1: checkout button copy", True),
    Family("may", date(2026, 5, 19), 200, (("Alder", .20), ("Birch", .10), ("Cedar", .40),
           ("Dune", .30)), ("Alder", "Birch"), "release v4.0.2: search ranking tweak", False),
    Family("jul", date(2026, 7, 7), 80, (("Kestrel", .25), ("Osprey", .25), ("Heron", .20),
           ("Plover", .30)), ("Kestrel", "Osprey", "Heron"),
           "release v1.9.0: new product images", True),
    Family("sep", date(2026, 9, 2), 300, (("Atlas", .22), ("Borealis", .18), ("Cobalt", .20),
           ("Delta", .25), ("Ember", .15)), ("Atlas",), "release v7.2.0: currency display",
           False),
    Family("oct", date(2026, 10, 14), 120, (("Quill", .35), ("Rook", .40), ("Sable", .25)),
           ("Quill",), "release v3.3.0: address autocomplete", True),
    Family("dec", date(2026, 12, 1), 150, (("Lumen", .30), ("Pyre", .20), ("Vesta", .25),
           ("Wick", .25)), ("Lumen", "Pyre"), "release v5.1.4: wishlist sharing", False),
)
STATES = ("load-stopped", "business-changed", "cannot-decide", "transform-defect")
LIVE = ("business-changed", "cannot-decide", "transform-defect")
# Version 2 (final plan, decision A2): the alert names the number it measured. Version 1 put
# the drop in orders under the word revenue; the orders fall by the same share in every state
# of a family and the revenue does not, so only the orders can stand in a shared alert. The
# version-1 packages are still written, byte for byte: rehearsals and the stage ran on them.
VERSION = 2
# a seventh company, generated after the burn, for the stage: the three live states only
DEMO = Family("aug", date(2026, 8, 18), 110, (("Juniper", .30), ("Kiln", .20), ("Larch", .25),
              ("Mistral", .25)), ("Juniper", "Kiln"), "release v6.0.1: saved carts", True)
DEMO_STATES = ("business-changed", "cannot-decide", "transform-defect")

STG = """-- stg_orders: the orders each nightly load committed, one row per order.
-- A batch is staged up to the line the loader acknowledged.
SELECT o.order_id, o.order_date, o.distributor, o.amount_usd
FROM raw_orders o
JOIN load_log l ON l.batch_id = o.batch_id
WHERE o.line_no <= l.rows_loaded;
"""


def staging(family: Family, state: str) -> str:
    """The staging transform in force. Where the staging change is wrong, a clause dated
    from the day, meant for sandbox test orders, names the family's live distributors."""
    if state != "transform-defect":
        return STG
    named = ", ".join(f"'{n}'" for n in family.leaving)
    return (STG.replace("-- A batch is staged up to the line the loader acknowledged.\n",
                        "-- A batch is staged up to the line the loader acknowledged.\n"
                        f"-- DATA-97: from {family.day}, leave the vendor's sandbox test orders "
                        "out of staging.\n")
            .replace("WHERE o.line_no <= l.rows_loaded;",
                     "WHERE o.line_no <= l.rows_loaded\n"
                     f"  AND NOT (o.order_date >= '{family.day}' AND o.distributor IN ({named}));"))


def body(sql: str) -> str:
    """A transform's statement, without its comment lines or its closing semicolon."""
    return "\n".join(line for line in sql.splitlines()
                     if not line.startswith("--")).strip().rstrip(";")


MART = """-- mart_daily_revenue: orders and revenue per day, from the staged orders.
SELECT order_date AS day, COUNT(*) AS orders, SUM(amount_usd) AS revenue_usd
FROM stg_orders
GROUP BY order_date;
"""
RAW_ORDERS_SCHEMA = {
    "source": "vendor.orders_feed", "schema_version": 2,
    "fields": {
        "order_id": {"meaning": "the vendor's order identifier, unique"},
        "batch_id": {"meaning": "the nightly delivery the order arrived in"},
        "line_no": {"meaning": "the order's line within its batch, from 1"},
        "order_date": {"meaning": "the day the order was placed"},
        "distributor": {"meaning": "the distributor that placed the order"},
        "amount_usd": {"meaning": "order value", "unit": "USD"},
    },
}
# the alerted metric, as a series a page can draw: read by the runtime from the frozen world
# before the investigation and by the validator from its rebuild — never shown to the model
ALERT_SERIES = {"metric": "Daily revenue", "unit": "USD",
                "query": "SELECT day, ROUND(revenue_usd, 2) AS revenue_usd "
                         "FROM mart_daily_revenue ORDER BY day"}
QUIET = {"bulletin": "The quarterly price list is unchanged.",
         "platform": "Maintenance windows are unchanged this month."}


def seed(family: Family) -> int:
    return int(hashlib.sha256(family.name.encode()).hexdigest()[:8], 16)


def incident_id(family: Family, state: str, version: int = VERSION) -> str:
    """Opaque: nothing in it says which family, state or version of the evidence it holds."""
    named = f"{seed(family)}:{family.name}:{state}" + (f":v{version}" if version > 1 else "")
    return "revenue-drop-" + hashlib.sha256(named.encode()).hexdigest()[:6]


def alert(family: Family, version: int = VERSION) -> str:
    """What the investigator is told, the same in every state of a family."""
    fell = round(100 * (1 - family.kept / family.per_day))
    if version == 1:
        return (f"Daily revenue for {family.day} fell about {fell}% against the previous two "
                "weeks. A release went out that morning, and product wants it rolled back.")
    return (f"Daily revenue for {family.day} fell sharply: the day counted about {fell}% fewer "
            "orders than a usual day. A release went out that morning, and product wants it "
            "rolled back.")


def orders_by_day(family: Family, state: str) -> list[tuple[date, list[str]]]:
    """Each day's orders as distributor names in line order: two weeks at about the
    family's volume, then the day the alert is about."""
    rng = random.Random(seed(family))
    days = []
    for back in range(HISTORY, 0, -1):
        total = rng.randint(round(family.per_day * .96), round(family.per_day * 1.04))
        mix = [n for n, s in family.shares for _ in range(round(total * s))]
        rng.shuffle(mix)
        days.append((family.day - timedelta(days=back), mix))
    full = {n: round(family.per_day * s) for n, s in family.shares}
    if state == "business-changed":                     # the leaving distributors stop
        today = {n: c for n, c in full.items() if n not in family.leaving}
    elif state == "cannot-decide":                        # fewer, from everyone alike
        today = {n: round(c * family.kept / family.per_day) for n, c in full.items()}
        today[family.shares[0][0]] += family.kept - sum(today.values())
    else:                                                 # every order arrives
        today = full
    mix = [n for n, c in today.items() for _ in range(c)]
    rng.shuffle(mix)
    days.append((family.day, mix))
    return days


def say(family: Family, state: str) -> dict[str, str]:
    """What the notices and the load log's note say. Implicit families say nothing
    telling: the evidence is only in the data."""
    if not family.explicit:
        return {**QUIET, "note": ""}
    leaving = " and ".join(family.leaving)
    return {
        "transform-defect": {"bulletin": "No changes to distributor agreements this month.",
                             "platform": "All ingestion services operated normally this month.",
                             "note": ""},
        "load-stopped": {"bulletin": "No changes to distributor agreements this month.",
                         "platform": "All ingestion services operated normally this month.",
                         "note": f"connection reset at line {family.kept}; batch partially "
                                 "committed"},
        "business-changed": {"bulletin": f"The {leaving} distribution "
                                         f"agreement{'s' if len(family.leaving) > 1 else ''} "
                                         f"ended on {family.day - timedelta(days=1)}. No "
                                         "further orders are expected.",
                             "platform": "All ingestion services operated normally this month.",
                             "note": ""},
        "cannot-decide": {"bulletin": "No changes to distributor agreements this month.",
                          "platform": "Delivery manifest service: since "
                                      f"{family.day - timedelta(days=2)} declared row counts "
                                      "may overstate the rows actually sent (known counting "
                                      "fault, PLAT-212, fix scheduled).",
                          "note": ""},
    }[state]


def world(family: Family, state: str) -> str:
    rng = random.Random(seed(family) + 1)
    raw, loads, manifest = [], [], []
    for day, mix in orders_by_day(family, state):
        batch, final = f"B-{day:%m%d}", day == family.day
        for line, distributor in enumerate(mix, start=1):
            raw.append(f"('{day:%m%d}-{line:03d}', '{batch}', {line}, '{day}', "
                       f"'{distributor}', {round(rng.uniform(20, 80), 2)})")
        stopped = final and state == "load-stopped"
        loaded = family.kept if stopped else len(mix)
        status = "FAILED" if stopped else "SUCCESS"
        note = say(family, state)["note"] if final else ""
        loads.append(f"('{batch}', '{day}', {len(mix)}, {loaded}, '{status}', '{note}')")
        declared = family.per_day if final and state == "cannot-decide" else len(mix)
        manifest.append(f"('{batch}', '{day}T02:00:00Z', {declared})")
    return "\n".join([
        "CREATE TABLE raw_orders (order_id TEXT PRIMARY KEY, batch_id TEXT, line_no INTEGER, "
        "order_date TEXT, distributor TEXT, amount_usd REAL);",
        "INSERT INTO raw_orders VALUES\n" + ",\n".join(raw) + ";",
        # the extract is partitioned by day, as a warehouse would keep it
        "CREATE INDEX raw_orders_by_day ON raw_orders (order_date);",
        "CREATE TABLE load_log (batch_id TEXT PRIMARY KEY, run_date TEXT, rows_received "
        "INTEGER, rows_loaded INTEGER, status TEXT, note TEXT);",
        "INSERT INTO load_log VALUES\n" + ",\n".join(loads) + ";",
        "CREATE TABLE delivery_manifest (batch_id TEXT PRIMARY KEY, sent_at TEXT, "
        "declared_rows INTEGER);",
        "INSERT INTO delivery_manifest VALUES\n" + ",\n".join(manifest) + ";",
        # the derived tables as the pipeline built them, from the transforms below
        "CREATE TABLE stg_orders AS " + body(staging(family, state)) + ";",
        "CREATE TABLE mart_daily_revenue AS " + body(MART) + ";",
    ]) + "\n"


def receipts(family: Family, state: str) -> str:
    lines = []
    for day, mix in orders_by_day(family, state):
        said = f"{len(mix)} rows sent"
        if day == family.day and state == "cannot-decide":
            said = "not received — vendor portal unavailable"
        lines.append(f"{day} B-{day:%m%d} vendor receipt: {said}")
    return "\n".join(lines) + "\n"


def changes(family: Family, state: str) -> str:
    staged = (f"| {family.day} | transforms/stg_orders.sql | DATA-97 | leave the vendor's "
              "sandbox test orders out of staging |\n") if state == "transform-defect" else ""
    return ("# Pipeline and release changes\n\n| date | file | ticket | change |\n"
            "| --- | --- | --- | --- |\n"
            f"| {family.day} | web/release.json | REL-231 | {family.release} |\n" + staged +
            "| 2026-02-20 | transforms/stg_orders.sql | DATA-88 | stage a batch up to the "
            "loader's acked line |\n"
            "| 2026-01-14 | transforms/mart_daily_revenue.sql | DATA-71 | daily revenue from "
            "staged orders |\n")


def package(family: Family, state: str, version: int = VERSION) -> dict[str, str]:
    """Every file of one incident package, by its path inside the package."""
    notices = say(family, state)
    def as_json(value: object) -> str:
        return json.dumps(value, indent=2) + "\n"
    return {
        "incident.json": as_json({"incident_id": incident_id(family, state, version),
                                  "alert": alert(family, version),
                                  "as_of": f"{family.day + timedelta(days=1)}T07:00:00Z",
                                  "permitted_write_paths": PERMITTED}),
        "world.sql": world(family, state),
        "transform_map.json": as_json({"stg_orders": "stg_orders.sql",
                                       "mart_daily_revenue": "mart_daily_revenue.sql"}),
        "transform_sources/stg_orders.sql": staging(family, state),
        "transform_sources/mart_daily_revenue.sql": MART,
        "notice_map.json": as_json({"commercial-bulletin": "commercial_bulletin.md",
                                    "platform-status": "platform_status.md"}),
        "notice_sources/commercial_bulletin.md": f"# Commercial bulletin\n\n"
                                                 f"{notices['bulletin']}\n",
        "notice_sources/platform_status.md": f"# Platform status\n\n{notices['platform']}\n",
        "change_history_map.json": as_json({"pipeline-changes": "CHANGE_HISTORY.md"}),
        "change_history_sources/CHANGE_HISTORY.md": changes(family, state),
        "reconciliation_map.json": as_json({"vendor-receipts": "vendor_receipts.log"}),
        "reconciliation_sources/vendor_receipts.log": receipts(family, state),
        "declared_schema_map.json": as_json({"raw_orders": "raw_orders.json"}),
        "declared_schema_sources/raw_orders.json": as_json(RAW_ORDERS_SCHEMA),
        "alert_series.json": as_json(ALERT_SERIES),
    }


def cases() -> list[tuple[Family, str]]:
    """The current version's cases: every live state of every family, and the demo's."""
    return [(f, s) for f in FAMILIES for s in LIVE] + [(DEMO, s) for s in DEMO_STATES]


def written() -> list[tuple[Family, str, int]]:
    """Every package this module writes: version 1 whole — the burned state included — and
    the current version's cases."""
    return [*((f, s, 1) for f in FAMILIES for s in STATES), *((DEMO, s, 1) for s in DEMO_STATES),
            *((f, s, VERSION) for f, s in cases())]


def packages() -> dict[str, dict[str, str]]:
    """Every package, by incident id, in id order — which says nothing about the states."""
    return dict(sorted((incident_id(f, s, v), package(f, s, v)) for f, s, v in written()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--into", default=str(INCIDENTS), metavar="DIR")
    args = parser.parse_args(argv)
    for incident, files in packages().items():
        for name, text in files.items():
            path = Path(args.into) / incident / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {Path(args.into) / incident}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
