"""Verify picking ingestion retains assignments, including unmatched locations."""

import csv
import hashlib
from pathlib import Path
import sqlite3

import pytest

from scripts.load_picks import load_picks
from scripts.load_products import load_products
from scripts.load_locations import load_locations


SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
HEADERS = ["waveNumber", "reference", "Size (US)", "quantityToPick (units)", "locations", "operator"]
VALID = [" 001 ", "PRODUCT_01", "9.5", "1", " A-01 ", " Operator_1 "]


@pytest.fixture
def database(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    product_path = tmp_path / "Product.csv"
    product_path.write_text("Reference;ABCCOD;Sector\nPRODUCT_01;A;PF\n", encoding="utf-8")
    load_products(connection, product_path)
    location_path = tmp_path / "Storage_Location.csv"
    location_path.write_text('originalLocation,position,x,y,z\nA-01,"1,2,3",1,2,3\n', encoding="utf-8")
    load_locations(connection, location_path)
    yield connection
    connection.close()


def write_source(tmp_path, rows, headers=HEADERS):
    path = tmp_path / "Picking_Wave.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)
    return path


def assert_no_picking_load(database):
    assert database.execute("SELECT count(*) FROM picking_records").fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (2,)
    assert database.execute("SELECT count(*) FROM products").fetchone() == (1,)
    assert database.execute("SELECT count(*) FROM locations").fetchone() == (1,)
    assert not database.in_transaction


def test_load_preserves_repeats_raw_size_and_unmatched_locations(database, tmp_path):
    unmatched = VALID.copy()
    unmatched[2], unmatched[4] = " 10.5 ", " UNKNOWN "
    path = write_source(tmp_path, [VALID, VALID, unmatched])
    original = path.read_bytes()
    assert load_picks(database, path) == 3
    assert database.execute(
        """SELECT wave_number,reference,size_raw,quantity,location_code,
                  operator_label,source_record_number
           FROM picking_records ORDER BY source_record_number"""
    ).fetchall() == [
        ("001", "PRODUCT_01", "9.5", 1, "A-01", "Operator_1", 1),
        ("001", "PRODUCT_01", "9.5", 1, "A-01", "Operator_1", 2),
        ("001", "PRODUCT_01", " 10.5 ", 1, "UNKNOWN", "Operator_1", 3),
    ]
    assert database.execute(
        "SELECT sha256,size_bytes,record_count FROM source_files WHERE file_name=?",
        (path.name,),
    ).fetchone() == (hashlib.sha256(original).hexdigest(), len(original), 3)
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []
    assert path.read_bytes() == original
    assert not database.in_transaction


@pytest.mark.parametrize("index,value", [
    (0, ""), (1, " "), (2, ""), (2, " "), (3, ""), (3, "-1"),
    (3, "1.5"), (3, "one"), (4, ""), (5, " "),
])
def test_bad_record_rolls_back_earlier_rows(database, tmp_path, index, value):
    bad = VALID.copy()
    bad[index] = value
    path = write_source(tmp_path, [VALID, bad])
    with pytest.raises(ValueError, match="Picking record 2"):
        load_picks(database, path)
    assert_no_picking_load(database)


def test_unknown_product_rolls_back_load(database, tmp_path):
    bad = VALID.copy()
    bad[1] = "UNKNOWN_PRODUCT"
    path = write_source(tmp_path, [VALID, bad])
    with pytest.raises(sqlite3.IntegrityError):
        load_picks(database, path)
    assert_no_picking_load(database)


@pytest.mark.parametrize("rows", [[], [VALID[:-1]], [VALID + ["extra"]]])
def test_empty_or_wrong_width_file_is_rejected(database, tmp_path, rows):
    path = write_source(tmp_path, rows)
    with pytest.raises(ValueError):
        load_picks(database, path)
    assert_no_picking_load(database)


def test_wrong_header_is_rejected(database, tmp_path):
    headers = HEADERS.copy()
    headers[1] = "Reference"
    path = write_source(tmp_path, [VALID], headers)
    with pytest.raises(ValueError, match="headers"):
        load_picks(database, path)
    assert_no_picking_load(database)


def test_repeat_load_leaves_existing_assignments_unchanged(database, tmp_path):
    path = write_source(tmp_path, [VALID])
    load_picks(database, path)
    with pytest.raises(sqlite3.IntegrityError):
        load_picks(database, path)
    assert database.execute("SELECT count(*),sum(quantity) FROM picking_records").fetchone() == (1, 1)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (3,)


def test_quantities_need_not_equal_one(database, tmp_path):
    rows = []
    for quantity in [0, 3]:
        row = VALID.copy()
        row[3] = str(quantity)
        rows.append(row)
    path = write_source(tmp_path, rows)
    assert load_picks(database, path) == 2
    assert database.execute("SELECT count(*),sum(quantity) FROM picking_records").fetchone() == (2, 3)


def test_wave_can_have_multiple_operators(database, tmp_path):
    second = VALID.copy()
    second[5] = "Operator_2"
    path = write_source(tmp_path, [VALID, second])
    load_picks(database, path)
    assert database.execute(
        "SELECT count(DISTINCT wave_number),count(DISTINCT operator_label) FROM picking_records"
    ).fetchone() == (1, 2)


def test_loader_does_not_require_location_or_order_records(database, tmp_path):
    database.execute("DELETE FROM locations")
    database.commit()
    path = write_source(tmp_path, [VALID])
    assert load_picks(database, path) == 1
    assert database.execute("SELECT count(*) FROM locations").fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM order_records").fetchone() == (0,)


def test_active_transaction_is_left_alone(database, tmp_path):
    path = write_source(tmp_path, [VALID])
    database.execute("BEGIN")
    with pytest.raises(ValueError, match="active transaction"):
        load_picks(database, path)
    assert database.in_transaction
    database.rollback()


def test_loader_enables_foreign_keys(database, tmp_path):
    path = write_source(tmp_path, [VALID])
    database.execute("PRAGMA foreign_keys = OFF")
    assert load_picks(database, path) == 1
    assert database.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_invalid_csv_syntax_rolls_back_load(database, tmp_path):
    path = tmp_path / "Picking_Wave.csv"
    path.write_text(';'.join(HEADERS) + '\n"unterminated;record\n', encoding="utf-8")
    with pytest.raises(csv.Error):
        load_picks(database, path)
    assert_no_picking_load(database)


@pytest.mark.parametrize("column,value", [
    ("wave_number", None), ("wave_number", ""), ("reference", "UNKNOWN_PRODUCT"),
    ("size_raw", None), ("size_raw", ""), ("quantity", -1), ("quantity", 1.5),
    ("location_code", None), ("location_code", " A "), ("operator_label", ""),
    ("source_file_id", 999), ("source_record_number", 0),
])
def test_schema_rejects_invalid_picking_fields(database, tmp_path, column, value):
    path = write_source(tmp_path, [VALID])
    load_picks(database, path)
    # Column names are fixed test cases, never external input.
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(f"UPDATE picking_records SET {column} = ?", (value,))


def test_source_record_cannot_be_claimed_twice(database, tmp_path):
    path = write_source(tmp_path, [VALID, VALID])
    load_picks(database, path)
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("UPDATE picking_records SET source_record_number = 1")
