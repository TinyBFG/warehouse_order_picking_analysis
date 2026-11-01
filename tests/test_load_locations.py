"""Check location parsing, source links, shared coordinates, and atomic loads."""

import csv
import hashlib
from pathlib import Path
import sqlite3

import pytest

from scripts.load_locations import load_locations
from scripts.load_products import load_products


SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def write_source(tmp_path, rows, headers=None):
    path = tmp_path / "Storage_Location.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers if headers is not None else
                        ["originalLocation", "position", "x", "y", "z"])
        writer.writerows(rows)
    return path


def test_load_keeps_shared_coordinates_source_text_and_metadata(database, tmp_path):
    path = write_source(tmp_path, [
        [" A-01 ", " 102, 810, 3 ", 102, 810, 3],
        ["A-02", "102,810,3", 102, 810, 3],
    ])
    original = path.read_bytes()
    assert load_locations(database, path) == 2
    assert database.execute(
        "SELECT location_code,position_raw,x,y,z,source_record_number "
        "FROM locations ORDER BY source_record_number"
    ).fetchall() == [
        ("A-01", " 102, 810, 3 ", 102, 810, 3, 1),
        ("A-02", "102,810,3", 102, 810, 3, 2),
    ]
    assert database.execute(
        "SELECT file_name,sha256,size_bytes,record_count FROM source_files"
    ).fetchone() == (path.name, hashlib.sha256(original).hexdigest(), len(original), 2)
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []
    assert path.read_bytes() == original
    assert not database.in_transaction


@pytest.mark.parametrize("row", [
    ["A", "1,2,3", 1, 2],
    ["A", "1,2,3", 1, 2, 3, "extra"],
    [" ", "1,2,3", 1, 2, 3],
    ["A", "1,2,3", "", 2, 3],
    ["A", "1,2,3", "one", 2, 3],
    ["A", "1.5,2,3", "1.5", 2, 3],
    ["A", "1,2,4", 1, 2, 3],
    ["A", "1,2", 1, 2, 3],
    ["A", "1,2,3,4", 1, 2, 3],
])
def test_bad_location_is_rejected_without_partial_load(database, tmp_path, row):
    path = write_source(tmp_path, [["VALID", "0,0,1", 0, 0, 1], row])
    with pytest.raises(ValueError):
        load_locations(database, path)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM locations").fetchone() == (0,)


@pytest.mark.parametrize("headers", [
    ["location", "position", "x", "y", "z"],
    ["originalLocation", "position", "y", "x", "z"],
])
def test_wrong_headers_are_rejected(database, tmp_path, headers):
    path = write_source(tmp_path, [["A", "1,2,3", 1, 2, 3]], headers)
    with pytest.raises(ValueError, match="headers"):
        load_locations(database, path)


def test_empty_file_is_rejected(database, tmp_path):
    path = write_source(tmp_path, [])
    with pytest.raises(ValueError, match="no data"):
        load_locations(database, path)


def test_duplicate_code_after_trimming_rolls_back_load(database, tmp_path):
    path = write_source(tmp_path, [["A", "1,2,3", 1, 2, 3], [" A ", "4,5,6", 4, 5, 6]])
    with pytest.raises(sqlite3.IntegrityError):
        load_locations(database, path)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM locations").fetchone() == (0,)
    assert not database.in_transaction


def test_repeat_load_leaves_existing_locations_unchanged(database, tmp_path):
    path = write_source(tmp_path, [["A", "1,2,3", 1, 2, 3]])
    load_locations(database, path)
    with pytest.raises(sqlite3.IntegrityError):
        load_locations(database, path)
    assert database.execute("SELECT count(*) FROM locations").fetchone() == (1,)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (1,)


def test_load_does_not_change_products(database, tmp_path):
    product_path = tmp_path / "Product.csv"
    product_path.write_text("Reference;ABCCOD;Sector\nX;A;PF\n", encoding="utf-8")
    load_products(database, product_path)
    path = write_source(tmp_path, [["A", "1,2,3", 1, 2, 3]])
    load_locations(database, path)
    assert database.execute("SELECT reference FROM products").fetchall() == [("X",)]
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (2,)


def test_active_transaction_is_left_alone(database, tmp_path):
    path = write_source(tmp_path, [["A", "1,2,3", 1, 2, 3]])
    database.execute("BEGIN")
    with pytest.raises(ValueError, match="active transaction"):
        load_locations(database, path)
    assert database.in_transaction
    database.rollback()


def test_loader_enables_foreign_keys(database, tmp_path):
    path = write_source(tmp_path, [["A", "-1,2,3", -1, 2, 3]])
    database.execute("PRAGMA foreign_keys = OFF")
    assert load_locations(database, path) == 1
    assert database.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_schema_rejects_location_without_source(database):
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(
            """INSERT INTO locations
               (location_code,position_raw,x,y,z,source_file_id,source_record_number)
               VALUES ('A','1,2,3',1,2,3,999,1)"""
        )


@pytest.mark.parametrize("column,value", [
    ("location_code", None), ("location_code", ""), ("position_raw", None),
    ("x", None), ("y", 1.5), ("source_record_number", 0),
])
def test_schema_rejects_invalid_location_fields(database, tmp_path, column, value):
    path = write_source(tmp_path, [["A", "1,2,3", 1, 2, 3]])
    load_locations(database, path)
    # Column names come from fixed test cases, never external input.
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(f"UPDATE locations SET {column} = ?", (value,))
