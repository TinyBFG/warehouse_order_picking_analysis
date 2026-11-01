"""Test product ingestion with small fixtures and an in-memory database."""

import csv
import hashlib
from pathlib import Path
import sqlite3

import pytest

from scripts.load_products import load_products


SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def write_source(tmp_path, rows, headers=None):
    path = tmp_path / "Product.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow(headers if headers is not None else ["Reference", "ABCCOD", "Sector"])
        writer.writerows(rows)
    return path


def test_load_preserves_values_metadata_and_record_order(database, tmp_path):
    path = write_source(tmp_path, [[" 001 ", "A", " PF  "], ["QUOTE'REF", "B", "PF"]])
    original = path.read_bytes()
    assert load_products(database, path) == 2
    assert database.execute(
        "SELECT reference, abc_code, sector, source_record_number "
        "FROM products ORDER BY source_record_number"
    ).fetchall() == [("001", "A", "PF", 1), ("QUOTE'REF", "B", "PF", 2)]
    assert database.execute(
        "SELECT file_name, sha256, size_bytes, record_count FROM source_files"
    ).fetchall() == [("Product.csv", hashlib.sha256(original).hexdigest(), len(original), 2)]
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []
    assert path.read_bytes() == original
    assert not database.in_transaction


@pytest.mark.parametrize("headers", [
    ["Reference", "Sector", "ABCCOD"], ["Reference", "ABCCOD"],
    ["Reference", "ABCCOD", "ABCCOD"], ["reference", "ABCCOD", "Sector"],
])
def test_unexpected_headers_leave_database_empty(database, tmp_path, headers):
    path = write_source(tmp_path, [["X", "A", "PF"]], headers)
    with pytest.raises(ValueError, match="headers"):
        load_products(database, path)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (0,)


@pytest.mark.parametrize("rows", [
    [], [["X", "A"]], [["X", "A", "PF", "extra"]],
    [["X", "A", "PF"], ["Y", "B", "   "]],
])
def test_empty_or_malformed_input_is_not_loaded(database, tmp_path, rows):
    path = write_source(tmp_path, rows)
    with pytest.raises(ValueError):
        load_products(database, path)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM products").fetchone() == (0,)


@pytest.mark.parametrize("rows", [
    [["X", "A", "PF"], ["X", "B", "PF"]],
    [["X", "A", "PF"], [" X ", "B", "PF"]],
    [["X", "A", "PF"], ["Y", "D", "PF"]],
])
def test_constraint_failure_rolls_back_products_and_metadata(database, tmp_path, rows):
    path = write_source(tmp_path, rows)
    with pytest.raises(sqlite3.IntegrityError):
        load_products(database, path)
    assert database.execute("SELECT count(*) FROM products").fetchone() == (0,)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (0,)
    assert not database.in_transaction


def test_repeat_load_does_not_replace_or_append(database, tmp_path):
    path = write_source(tmp_path, [["X", "A", "PF"]])
    load_products(database, path)
    with pytest.raises(sqlite3.IntegrityError):
        load_products(database, path)
    assert database.execute("SELECT count(*) FROM products").fetchone() == (1,)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (1,)


def test_failed_second_file_preserves_existing_data(database, tmp_path):
    path = write_source(tmp_path, [["X", "A", "PF"]])
    load_products(database, path)
    other = tmp_path / "OtherProduct.csv"
    other.write_text("Reference;ABCCOD;Sector\nY;B;PF\nX;C;PF\n", encoding="utf-8")
    with pytest.raises(sqlite3.IntegrityError):
        load_products(database, other)
    assert database.execute("SELECT reference FROM products").fetchall() == [("X",)]
    assert database.execute("SELECT file_name FROM source_files").fetchall() == [("Product.csv",)]


def test_active_transaction_is_not_committed_or_rolled_back(database, tmp_path):
    path = write_source(tmp_path, [["X", "A", "PF"]])
    database.execute("BEGIN")
    with pytest.raises(ValueError, match="active transaction"):
        load_products(database, path)
    assert database.in_transaction
    database.rollback()


def test_loader_enables_foreign_keys_on_its_connection(database, tmp_path):
    path = write_source(tmp_path, [["X", "A", "PF"]])
    database.execute("PRAGMA foreign_keys = OFF")
    assert load_products(database, path) == 1
    assert database.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_invalid_csv_syntax_does_not_register_source(database, tmp_path):
    path = tmp_path / "Product.csv"
    path.write_text('Reference;ABCCOD;Sector\n"unterminated;A;PF\n', encoding="utf-8")
    with pytest.raises(csv.Error):
        load_products(database, path)
    assert database.execute("SELECT count(*) FROM source_files").fetchone() == (0,)
