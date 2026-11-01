"""Verify schema behavior using in-memory SQLite and small synthetic records."""

from pathlib import Path
import sqlite3

import pytest


SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


@pytest.fixture
def database():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA.read_text(encoding="utf-8"))
    yield connection
    connection.close()


def register_source(database, **overrides):
    values = {
        "file_name": "Product.csv", "sha256": "a" * 64,
        "size_bytes": 100, "record_count": 2,
    }
    values.update(overrides)
    cursor = database.execute(
        """INSERT INTO source_files (file_name, sha256, size_bytes, record_count)
           VALUES (:file_name, :sha256, :size_bytes, :record_count)""", values,
    )
    return cursor.lastrowid


def insert_product(database, source_id, **overrides):
    values = {
        "reference": "EXAMPLE_001", "abc_code": "A", "sector": "PF",
        "source_file_id": source_id, "source_record_number": 1,
    }
    values.update(overrides)
    database.execute(
        """INSERT INTO products
           (reference, abc_code, sector, source_file_id, source_record_number)
           VALUES (:reference, :abc_code, :sector, :source_file_id,
                   :source_record_number)""", values,
    )


def test_valid_product_retains_source_relationship(database):
    source_id = register_source(database)
    insert_product(database, source_id)
    result = database.execute(
        """SELECT p.reference, p.abc_code, p.sector, s.file_name,
                  p.source_record_number
           FROM products AS p
           JOIN source_files AS s ON p.source_file_id = s.source_file_id"""
    ).fetchall()
    assert result == [("EXAMPLE_001", "A", "PF", "Product.csv", 1)]
    assert database.execute("PRAGMA foreign_keys").fetchone() == (1,)
    assert database.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("overrides", [
    {"file_name": None}, {"file_name": ""}, {"file_name": " Product.csv "},
    {"sha256": None}, {"sha256": "a" * 63}, {"sha256": "g" * 64},
    {"size_bytes": None}, {"size_bytes": -1}, {"size_bytes": 1.5},
    {"record_count": None}, {"record_count": -1}, {"record_count": 1.5},
])
def test_invalid_source_metadata_is_rejected(database, overrides):
    with pytest.raises(sqlite3.IntegrityError):
        register_source(database, **overrides)


def test_duplicate_filename_is_rejected(database):
    register_source(database)
    with pytest.raises(sqlite3.IntegrityError):
        register_source(database, sha256="b" * 64)


@pytest.mark.parametrize("overrides", [
    {"reference": None}, {"reference": ""}, {"reference": " EXAMPLE_001 "},
    {"abc_code": None}, {"abc_code": "D"},
    {"sector": None}, {"sector": ""}, {"sector": "PF "},
    {"source_file_id": None}, {"source_record_number": None},
    {"source_record_number": 0}, {"source_record_number": 1.5},
])
def test_invalid_product_is_rejected(database, overrides):
    source_id = register_source(database)
    with pytest.raises(sqlite3.IntegrityError):
        insert_product(database, source_id, **overrides)


def test_duplicate_reference_is_rejected(database):
    source_id = register_source(database)
    insert_product(database, source_id)
    with pytest.raises(sqlite3.IntegrityError):
        insert_product(database, source_id, source_record_number=2)


def test_two_products_cannot_claim_the_same_source_record(database):
    source_id = register_source(database)
    insert_product(database, source_id)
    with pytest.raises(sqlite3.IntegrityError):
        insert_product(database, source_id, reference="EXAMPLE_002")


def test_product_cannot_reference_missing_source(database):
    with pytest.raises(sqlite3.IntegrityError):
        insert_product(database, 999)


def test_referenced_source_cannot_be_deleted(database):
    source_id = register_source(database)
    insert_product(database, source_id)
    with pytest.raises(sqlite3.IntegrityError):
        database.execute("DELETE FROM source_files WHERE source_file_id = ?",
                         (source_id,))


def test_record_numbers_are_scoped_to_source_file(database):
    first = register_source(database)
    second = register_source(database, file_name="OtherProduct.csv")
    insert_product(database, first)
    insert_product(database, second, reference="EXAMPLE_002")
    assert database.execute("SELECT count(*) FROM products").fetchone() == (2,)
