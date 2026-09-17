"""Read-only is a property of the database, not of the query text (CONFORMANCE B4), and
every result is bounded (B2). These tests try to get past the authorizer the ways a model
would, and check that what comes back is a refusal the model can read."""
from __future__ import annotations

import sqlite3

import pytest
from adii.tools import Denied, ReadOnlyDatabase, Rejected

BUILD = """
CREATE TABLE orders (order_id TEXT PRIMARY KEY, amount_cents INTEGER NOT NULL);
INSERT INTO orders VALUES ('a', 100), ('b', 250), ('c', 75);
CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT, raw BLOB);
INSERT INTO notes VALUES (1, 'short', X'0102'), (2, '%s', NULL);
""" % ("x" * 2_000)


@pytest.fixture
def db() -> ReadOnlyDatabase:
    return ReadOnlyDatabase.in_memory(BUILD)


def count(db: ReadOnlyDatabase) -> int:
    return db.query("SELECT count(*) FROM orders", max_rows=1).rows[0][0]


class TestReadOnly:
    @pytest.mark.parametrize("sql", [
        "INSERT INTO orders VALUES ('d', 1)",
        "UPDATE orders SET amount_cents = 0",
        "DELETE FROM orders",
        "DROP TABLE orders",
        "CREATE TABLE scratch (x)",
        "CREATE TEMP TABLE scratch (x)",
        "ALTER TABLE orders ADD COLUMN y",
        "BEGIN",
        "VACUUM",
    ])
    def test_b4_every_write_is_denied_and_nothing_changes(self, db, sql):
        with pytest.raises(Denied, match="read-only"):
            db.query(sql, max_rows=10)
        assert count(db) == 3

    def test_attach_cannot_reach_another_file(self, db, tmp_path):
        other = tmp_path / "answer_key.db"
        sqlite3.connect(other).close()
        with pytest.raises(Denied, match="ATTACH"):
            db.query(f"ATTACH DATABASE '{other.as_posix()}' AS key", max_rows=1)

    def test_pragma_is_denied(self, db):
        with pytest.raises(Denied, match="PRAGMA"):
            db.query("PRAGMA table_info(orders)", max_rows=10)

    def test_load_extension_is_denied_even_as_a_function(self, db):
        with pytest.raises(Denied, match="load_extension"):
            db.query("SELECT load_extension('evil')", max_rows=1)

    def test_a_write_hidden_in_a_cte_is_still_denied(self, db):
        with pytest.raises(Denied):
            db.query("WITH x AS (SELECT 1) INSERT INTO orders SELECT 'z', 1 FROM x", max_rows=1)

    def test_a_denial_says_what_was_refused(self, db):
        with pytest.raises(Denied, match="DELETE orders"):
            db.query("DELETE FROM orders", max_rows=1)


class TestRejected:
    def test_a_syntax_error_is_the_models_mistake(self, db):
        with pytest.raises(Rejected, match="syntax error"):
            db.query("SELEC 1", max_rows=1)

    def test_an_unknown_table_is_the_models_mistake(self, db):
        with pytest.raises(Rejected, match="no such table"):
            db.query("SELECT * FROM customers", max_rows=1)

    def test_two_statements_are_one_too_many(self, db):
        with pytest.raises(Rejected, match="one statement"):
            db.query("SELECT 1; DELETE FROM orders", max_rows=1)
        assert count(db) == 3

    def test_an_empty_query_is_rejected(self, db):
        with pytest.raises(Rejected, match="empty"):
            db.query("   ", max_rows=1)

    def test_a_runaway_query_is_interrupted_and_sent_back(self):
        db = ReadOnlyDatabase.in_memory(BUILD, max_progress_ticks=2)
        with pytest.raises(Rejected, match="execution budget"):
            db.query("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) "
                     "SELECT count(*) FROM c", max_rows=1)
        assert count(db) == 3, "the connection is still usable afterwards"


class TestBounded:
    def test_b2_rows_are_capped_and_the_cap_is_reported(self, db):
        result = db.query("SELECT * FROM orders ORDER BY order_id", max_rows=2)
        assert len(result.rows) == 2 and result.truncated is True
        assert result.columns == ("order_id", "amount_cents")

    def test_a_result_inside_the_cap_is_not_marked_truncated(self, db):
        result = db.query("SELECT * FROM orders", max_rows=3)
        assert len(result.rows) == 3 and result.truncated is False

    def test_long_cells_are_cut_and_say_so(self, db):
        result = db.query("SELECT body FROM notes WHERE id = 2", max_rows=1)
        cell = result.rows[0][0]
        assert len(cell) < 600 and "truncated, 2000 chars" in cell

    def test_blobs_and_non_finite_floats_become_json_safe_text(self, db):
        result = db.query("SELECT raw, 1e308 * 10 FROM notes WHERE id = 1", max_rows=1)
        assert result.rows[0] == ("<blob 2 bytes>", "inf")

    @pytest.mark.parametrize("bad", [0, -1, True])
    def test_a_disabled_row_cap_is_refused(self, db, bad):
        with pytest.raises(ValueError):
            db.query("SELECT 1", max_rows=bad)


class TestSchema:
    def test_tables_are_listed_without_sqlite_internals(self, db):
        assert db.tables() == ("notes", "orders")

    def test_a_table_schema_has_columns_and_its_ddl(self, db):
        schema = db.schema("orders")
        assert schema.columns == ("order_id", "amount_cents")
        assert schema.ddl.startswith("CREATE TABLE orders")

    def test_an_unknown_table_is_rejected_and_the_known_ones_named(self, db):
        with pytest.raises(Rejected, match="notes"):
            db.schema("customers")
        # and a query that names one: the same answer, so a guess can be corrected rather
        # than turned into a finding (R0 of 17 Sep concluded a table was "missing")
        with pytest.raises(Rejected, match="no such table.*known tables.*notes"):
            db.query("SELECT * FROM customers", max_rows=5)


class TestFromFile:
    def test_b3_the_path_is_configuration_and_the_file_opens_read_only(self, tmp_path):
        path = tmp_path / "world.db"
        con = sqlite3.connect(path)
        con.executescript(BUILD)
        con.close()
        db = ReadOnlyDatabase.from_file(path)
        assert count(db) == 3
        with pytest.raises(Denied):
            db.query("DELETE FROM orders", max_rows=1)
        db.close()
        assert sqlite3.connect(path).execute("SELECT count(*) FROM orders").fetchone() == (3,)

    def test_a_missing_file_is_an_error_at_construction_not_at_query_time(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ReadOnlyDatabase.from_file(tmp_path / "nope.db")
