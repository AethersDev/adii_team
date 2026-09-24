"""A world from the operator's own files — the door through which uploaded data becomes the
same read-only SQLite world every other incident has, so the investigator, the tools, the
runtime and the archive need no second path for it.

CSV only, for now: one table per file, named after the file; every column typed from its
values (INTEGER when every value is a whole number, REAL when every value is a number, TEXT
otherwise; a blank cell is NULL) and never altered by the typing — a value that would not
survive the conversion exactly keeps its column text; a header alone is an empty table;
bounded in files, columns, rows and size, and refused with the reason when a file is not
that. Pure text: this module opens nothing and knows no path. The server hands it the
files' contents and gets back the build script that `ReadOnlyDatabase.in_memory` runs —
which is exactly what a specimen's world is.
"""
from __future__ import annotations

import csv
import io
import math
import re
from decimal import Decimal

LIMITS = {"files": 8, "columns": 64, "rows": 20_000, "chars": 2_000_000}
# ASCII digits only, no leading zeros, within SQLite's 64-bit integer, finite: a value that
# would change on the way in — "00012", an Arabic-Indic numeral, an integer past 64 bits,
# 1e400 — stays the text it was.
_DIGITS = re.compile(r"-?[0-9]+")
_INTEGER = re.compile(r"-?(0|[1-9][0-9]*)")
_REAL = re.compile(r"-?((0|[1-9][0-9]*)(\.[0-9]*)?|\.[0-9]+)([eE][-+]?[0-9]+)?")


def table_name(filename: str) -> str:
    """The table a file becomes: its name without the extension, as one SQL identifier."""
    stem = re.sub(r"\.csv$", "", filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1], flags=re.I)
    name = re.sub(r"[^A-Za-z0-9_]+", "_", stem).strip("_").lower()
    if not name:
        raise ValueError(f"{filename!r} gives no table name; name the file after its table")
    if name.startswith("sqlite_"):
        raise ValueError(f"{filename!r}: names beginning sqlite_ are SQLite's own")
    return name if not name[0].isdigit() else f"t_{name}"


def _column_names(header: list[str]) -> list[str]:
    names: list[str] = []
    for i, raw in enumerate(header):
        name = re.sub(r"[^A-Za-z0-9_]+", "_", raw.strip()).strip("_").lower() or f"column_{i + 1}"
        if name[0].isdigit():
            name = f"c_{name}"
        while name in names:                          # two headers that sanitise alike
            name += "_"
        names.append(name)
    return names


def _exact_real(value: str) -> bool:
    """A number a float holds without losing a digit: 1.10 is 1.1, and 3.14159265358979323846
    is not 3.141592653589793."""
    if not _REAL.fullmatch(value) or not math.isfinite(float(value)):
        return False
    return Decimal(value) == Decimal(repr(float(value)))     # _REAL has made it a number


def _typed(values: list[str]) -> str:
    present = [v for v in values if v != ""]
    if not present:
        return "TEXT"
    if all(_DIGITS.fullmatch(v) for v in present):          # whole numbers: exact or text
        return "INTEGER" if all(_INTEGER.fullmatch(v) and len(v.lstrip("-")) <= 19
                                and abs(int(v)) < 2 ** 63 for v in present) else "TEXT"
    if all(_exact_real(v) for v in present):
        return "REAL"
    return "TEXT"


def _literal(value: str, kind: str) -> str:
    if value == "":
        return "NULL"
    if kind == "INTEGER":
        return str(int(value))
    if kind == "REAL":
        return repr(float(value))
    return "'" + value.replace("'", "''") + "'"


def sql_from_csv(table: str, text: str) -> str:
    """One CSV file as the SQL that creates and fills one table; ValueError names what is
    wrong with a file this world will not take."""
    if len(text) > LIMITS["chars"]:
        raise ValueError(f"{table}: a file is limited to {LIMITS['chars']:,} characters")
    if "\x00" in text:
        raise ValueError(f"{table}: the file contains a NUL byte; it is not text")
    reader = csv.reader(io.StringIO(text))
    try:            # each row with the file line it ended on; a row with no content is skipped
        rows = [(reader.line_num, [c.strip() for c in row]) for row in reader
                if any(cell.strip() for cell in row)]
    except csv.Error as bad:
        raise ValueError(f"{table}: not a CSV this world can read — {bad}") from None
    if not rows:                          # a header alone is an empty table, which is a table
        raise ValueError(f"{table}: a CSV needs a header row")
    header, body = rows[0][1], rows[1:]
    if len(header) > LIMITS["columns"]:
        raise ValueError(f"{table}: a table is limited to {LIMITS['columns']} columns")
    if len(body) > LIMITS["rows"]:
        raise ValueError(f"{table}: a table is limited to {LIMITS['rows']:,} rows")
    for line, row in body:
        if len(row) != len(header):
            raise ValueError(f"{table}: line {line} has {len(row)} values for "
                             f"{len(header)} columns")
    body = [row for _, row in body]
    names = _column_names(header)
    kinds = [_typed([row[i] for row in body]) for i in range(len(names))]
    create = (f'CREATE TABLE "{table}" ('
              + ", ".join(f'"{n}" {k}' for n, k in zip(names, kinds, strict=True)) + ");")
    values = ",\n".join("(" + ", ".join(_literal(v, k) for v, k in zip(row, kinds, strict=True))
                        + ")" for row in body)
    return f'{create}\n' + (f'INSERT INTO "{table}" VALUES\n{values};\n' if body else "")


def world_from_files(files: list[tuple[str, str]]) -> str:
    """The build script for a world made of these (filename, contents) pairs: one table each,
    all distinct. What a specimen declares by hand, an upload declares by its files."""
    if not 1 <= len(files) <= LIMITS["files"]:
        raise ValueError(f"a world is made of 1 to {LIMITS['files']} CSV files")
    tables = [table_name(name) for name, _ in files]
    for name in tables:
        if tables.count(name) > 1:
            raise ValueError(f"two files would both become the table {name!r}")
    return "".join(sql_from_csv(table, text) for table, (_, text) in zip(tables, files,
                                                                          strict=True))
