"""Verify order loading preserves source records and rejects invalid inputs."""

import csv
import hashlib
from pathlib import Path
import sqlite3

import pytest

from scripts.load_orders import load_orders
from scripts.load_products import load_products


SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
HEADERS = ["codCustomer", "orderNumber", "orderToCollect", "Reference", "Size (US)",
           "quantity (units)", "creationDate", "waveNumber", "operator"]
VALID = [" CUSTOMER_01 ", "001", "1", "PRODUCT_01", "95", "2",
         "05/01/2023 07:42", "010", "Operator_1"]


@pytest.fixture
def database(tmp_path):
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    product_path = tmp_path / "Product.csv"
    product_path.write_text("Reference;ABCCOD;Sector\nPRODUCT_01;A;PF\n", encoding="utf-8")
    load_products(connection, product_path)
    yield connection
    connection.close()


def write_source(tmp_path, rows, headers=HEADERS):
    path = tmp_path / "Customer_Order.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)
    return path


def assert_no_order_load(database):
    assert database.execute("SELECT count(*) FROM order_records").fetchone() == (0,)
    assert database.execute("SELECT file_name FROM source_files").fetchall() == [("Product.csv",)]
    assert database.execute("SELECT count(*) FROM products").fetchone() == (1,)
    assert not database.in_transaction


def test_preserves_repeats_zero_quantity_missing_sizes_and_source_links(database, tmp_path):
    missing = VALID.copy()
    missing[4], missing[5] = "", "0"
    padded_size = VALID.copy()
    padded_size[4] = " 105 "
    path = write_source(tmp_path, [VALID, VALID, missing, padded_size])
    original = path.read_bytes()
    assert load_orders(database, path) == 4
    assert database.execute(
        """SELECT customer_code,order_number,order_to_collect,reference,size_raw,
                  quantity,created_at,wave_number,operator_label,source_record_number
           FROM order_records ORDER BY source_record_number"""
    ).fetchall() == [
        ("CUSTOMER_01", "001", 1, "PRODUCT_01", "95", 2, "2023-01-05 07:42", "010", "Operator_1", 1),
        ("CUSTOMER_01", "001", 1, "PRODUCT_01", "95", 2, "2023-01-05 07:42", "010", "Operator_1", 2),
        ("CUSTOMER_01", "001", 1, "PRODUCT_01", "", 0, "2023-01-05 07:42", "010", "Operator_1", 3),
        ("CUSTOMER_01", "001", 1, "PRODUCT_01", " 105 ", 2, "2023-01-05 07:42", "010", "Operator_1", 4),
    ]
    assert database.execute(
        "SELECT sha256,size_bytes,record_count FROM source_files WHERE file_name=?",
        (path.name,),
    ).fetchone() == (hashlib.sha256(original).hexdigest(), len(original), 4)
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []
    assert path.read_bytes() == original
    assert not database.in_transaction


@pytest.mark.parametrize("index,value", [
    (0, " "), (1, ""), (2, "0"), (2, "1.5"), (2, "one"),
    (3, ""), (5, "-1"), (5, "2.5"), (5, ""),
    (6, "31/02/2023 07:00"), (6, "2023-01-05"), (7, ""), (8, ""),
])
def test_bad_record_rolls_back_earlier_order_and_metadata(database, tmp_path, index, value):
    bad = VALID.copy()
    bad[index] = value
    path = write_source(tmp_path, [VALID, bad])
    with pytest.raises(ValueError, match="Order record 2"):
        load_orders(database, path)
    assert_no_order_load(database)


def test_unknown_product_rolls_back_earlier_records(database, tmp_path):
    bad = VALID.copy()
    bad[3] = "UNKNOWN"
    path = write_source(tmp_path, [VALID, bad])
    with pytest.raises(sqlite3.IntegrityError):
        load_orders(database, path)
    assert_no_order_load(database)


@pytest.mark.parametrize("rows", [[], [VALID[:-1]], [VALID + ["extra"]]])
def test_empty_or_wrong_width_input_is_rejected(database, tmp_path, rows):
    path = write_source(tmp_path, rows)
    with pytest.raises(ValueError):
        load_orders(database, path)
    assert_no_order_load(database)


def test_wrong_header_is_rejected(database, tmp_path):
    headers = HEADERS.copy()
    headers[3] = "reference"
    path = write_source(tmp_path, [VALID], headers)
    with pytest.raises(ValueError, match="headers"):
        load_orders(database, path)
    assert_no_order_load(database)


def test_repeat_load_does_not_append_or_replace(database, tmp_path):
    path = write_source(tmp_path, [VALID])
    load_orders(database, path)
    with pytest.raises(sqlite3.IntegrityError):
        load_orders(database, path)
    assert database.execute("SELECT count(*),sum(quantity) FROM order_records").fetchone() == (1, 2)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (2,)


def test_order_can_span_multiple_waves_and_operators(database, tmp_path):
    second = VALID.copy()
    second[7], second[8] = "011", "Operator_2"
    path = write_source(tmp_path, [VALID, second])
    assert load_orders(database, path) == 2
    assert database.execute(
        "SELECT count(DISTINCT order_number),count(DISTINCT wave_number),"
        "count(DISTINCT operator_label) FROM order_records"
    ).fetchone() == (1, 2, 2)


def test_active_transaction_is_left_alone(database, tmp_path):
    path = write_source(tmp_path, [VALID])
    database.execute("BEGIN")
    with pytest.raises(ValueError, match="active transaction"):
        load_orders(database, path)
    assert database.in_transaction
    database.rollback()


def test_loader_enables_foreign_keys(database, tmp_path):
    path = write_source(tmp_path, [VALID])
    database.execute("PRAGMA foreign_keys = OFF")
    assert load_orders(database, path) == 1
    assert database.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_invalid_csv_syntax_rolls_back_load(database, tmp_path):
    path = tmp_path / "Customer_Order.csv"
    path.write_text(';'.join(HEADERS) + '\n"unterminated;record\n', encoding="utf-8")
    with pytest.raises(csv.Error):
        load_orders(database, path)
    assert_no_order_load(database)


@pytest.mark.parametrize("column,value", [
    ("customer_code", None), ("order_number", ""), ("quantity", -1),
    ("quantity", 1.5), ("size_raw", None), ("reference", "UNKNOWN"),
    ("source_file_id", 999), ("source_record_number", 0),
])
def test_schema_rejects_invalid_order_fields(database, tmp_path, column, value):
    path = write_source(tmp_path, [VALID])
    load_orders(database, path)
    # Column identifiers are fixed test cases, not external input.
    with pytest.raises(sqlite3.IntegrityError):
        database.execute(f"UPDATE order_records SET {column} = ?", (value,))


def test_source_record_cannot_be_claimed_twice(database, tmp_path):
    path = write_source(tmp_path, [VALID, VALID])
    load_orders(database, path)
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("UPDATE order_records SET source_record_number = 1")
