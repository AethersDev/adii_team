"""An upload becomes the same world every incident has: CSV in, the build script
`ReadOnlyDatabase.in_memory` runs out — typed from the values, bounded, refused with the
reason when a file is not a table."""
from __future__ import annotations

import pytest
from adii.contracts import ToolCall
from adii.tools import ReadOnlyDatabase, build_sql_tools
from adii.tools.user_world import LIMITS, sql_from_csv, table_name, world_from_files

REVENUE = "day,revenue,region\n2026-03-07,1200.50,north\n2026-03-08,660,north\n2026-03-09,,south\n"


def test_a_csv_becomes_one_typed_table_and_blank_cells_are_null():
    script = sql_from_csv("revenue", REVENUE)
    assert 'CREATE TABLE "revenue" ("day" TEXT, "revenue" REAL, "region" TEXT);' in script
    assert "('2026-03-09', NULL, 'south')" in script
    assert ReadOnlyDatabase.in_memory(script).schema("revenue").columns == \
        ("day", "revenue", "region")


def test_the_world_is_queryable_through_the_tool_layer_only():
    tools = build_sql_tools(ReadOnlyDatabase.in_memory(world_from_files([
        ("Revenue.CSV", REVENUE),
        ("contracts.csv", "id,distributor,ended\n1,Northwind,2026-03-08\n")])))
    schema = tools.execute(ToolCall(call_id="c1", name="get_schema", arguments={}))
    assert schema.ok
    assert sorted(t["name"] for t in schema.content["tables"]) == ["contracts", "revenue"]
    rows = tools.execute(ToolCall(call_id="c2", name="run_sql", arguments={
        "query": "SELECT count(*) AS n, sum(revenue) AS total FROM revenue"}))
    assert rows.ok and rows.content["rows"][0] == [3, 1860.5]   # three rows, one NULL revenue
    assert not tools.execute(ToolCall(call_id="c3", name="run_sql", arguments={
        "query": "DELETE FROM revenue"})).ok


def test_identifiers_are_sanitised_and_values_quoted():
    script = sql_from_csv("t", "Order ID,amount $,1st,,name\n1,2,3,4,O'Brien\n1,2,3,4,x\n")
    assert '"order_id" INTEGER, "amount" INTEGER, "c_1st" INTEGER, "column_4" INTEGER, ' \
           '"name" TEXT' in script
    assert "'O''Brien'" in script
    assert table_name("/tmp/My Sales 2026.csv") == "my_sales_2026"
    assert table_name("2026.csv") == "t_2026"
    with pytest.raises(ValueError, match="no table name"):
        table_name("...csv")


def test_a_value_that_would_change_on_the_way_in_stays_text():
    """Typing never alters data: leading zeros, non-ASCII numerals, integers past 64 bits or
    past Python's digit limit, numbers past a float's range, and decimals a float cannot
    hold exactly are kept as the text they were; 1.10 is 1.1 and stays a number."""
    kept = ("zip,arabic,big,huge,long,precise,plain,price\n"
            f"00012,١٢٣,99999999999999999999999,1e400,{'9' * 5000},3.14159265358979323846,7,1.10\n")
    script = sql_from_csv("t", kept)
    assert ('"zip" TEXT, "arabic" TEXT, "big" TEXT, "huge" TEXT, "long" TEXT, "precise" TEXT, '
            '"plain" INTEGER, "price" REAL') in script
    assert "'00012', '١٢٣', '99999999999999999999999', '1e400', '9" in script
    assert "'3.14159265358979323846', 7, 1.1)" in script
    ReadOnlyDatabase.in_memory(script)                      # and it is a world SQLite takes


def test_a_file_that_is_not_a_table_is_refused_with_the_reason():
    with pytest.raises(ValueError, match="NUL byte"):
        sql_from_csv("t", "a,b\n1,x\x00y\n")
    with pytest.raises(ValueError, match="not a CSV this world can read"):
        sql_from_csv("t", "a,b\r1,2\r")                       # bare CR: csv.Error, as a reason
    with pytest.raises(ValueError, match="not a CSV this world can read"):
        sql_from_csv("t", "a\n" + "x" * 131_073 + "\n")     # past csv's own field limit
    with pytest.raises(ValueError, match="SQLite's own"):
        table_name("sqlite_master.csv")
    # the line named is the file's line, past blank lines and a newline inside a cell
    with pytest.raises(ValueError, match="line 6 has 1 values for 2 columns"):
        sql_from_csv("t", 'a,b\n\n"x\ny",2\n\n3\n')
    with pytest.raises(ValueError, match="needs a header row"):
        sql_from_csv("t", "\n\n")
    assert ReadOnlyDatabase.in_memory(sql_from_csv("t", "a,b\n")).schema("t").columns == \
        ("a", "b")                                      # a header alone: an empty table
    with pytest.raises(ValueError, match="line 3 has 1 values for 2 columns"):
        sql_from_csv("t", "a,b\n1,2\n3\n")
    with pytest.raises(ValueError, match="limited to"):
        sql_from_csv("t", "a\n" + "1\n" * (LIMITS["rows"] + 1))
    with pytest.raises(ValueError, match="columns"):
        sql_from_csv("t", ",".join("c" * 1 + str(i) for i in range(LIMITS["columns"] + 1)) + "\n"
                     + ",".join("1" for _ in range(LIMITS["columns"] + 1)) + "\n")
    with pytest.raises(ValueError, match="characters"):
        sql_from_csv("t", "a\n" + "x" * LIMITS["chars"])
    with pytest.raises(ValueError, match="1 to 8"):
        world_from_files([])
    with pytest.raises(ValueError, match="both become the table"):
        world_from_files([("a.csv", "x\n1\n"), ("A.csv", "x\n1\n")])


def test_every_specimen_world_survives_the_round_trip_through_csv(tmp_path):
    """The data to bring: `python -m adii.examples.specimens --csv DIR` writes each world as
    CSV files, and read back through the world builder every table holds the same rows —
    up to the one thing CSV cannot say, an empty string against NULL, which becomes NULL."""
    from adii.examples.specimens import SPECIMENS, write_csv
    write_csv(tmp_path)
    for specimen in SPECIMENS:
        folder = tmp_path / specimen.context.incident_id
        assert (folder / "alert.txt").read_text(encoding="utf-8").strip() == specimen.context.alert
        files = [(p.name, p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.csv"))]
        brought = ReadOnlyDatabase.in_memory(world_from_files(files))
        declared = ReadOnlyDatabase.in_memory(specimen.world)
        assert brought.tables() == declared.tables()
        def rows(world, table):
            found = world.query(f'SELECT * FROM "{table}" ORDER BY 1', max_rows=1000).rows
            return [tuple(None if v == "" else v for v in r) for r in found]
        for table in declared.tables():
            assert rows(brought, table) == rows(declared, table), \
                (specimen.context.incident_id, table)


def test_the_committed_csv_folder_is_what_the_specimens_generate(tmp_path):
    """01_data/demo/csv is generated from the specimens and committed so the data to bring
    is in the repository; it is held to its source the way the briefing and the identity
    are — regenerate with `python -m adii.examples.specimens --csv 01_data/demo/csv`."""
    from pathlib import Path

    from adii.examples.specimens import write_csv
    committed = Path(__file__).resolve().parents[3] / "01_data" / "demo" / "csv"
    for fresh in write_csv(tmp_path):
        kept = committed / fresh.relative_to(tmp_path)
        assert kept.is_file(), f"{kept} is missing; regenerate the folder"
        assert kept.read_bytes() == fresh.read_bytes(), f"{kept} is stale; regenerate the folder"
    for alert in tmp_path.glob("*/alert.txt"):
        assert (committed / alert.relative_to(tmp_path)).read_bytes() == alert.read_bytes()
