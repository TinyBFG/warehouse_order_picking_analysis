"""Verify relationship counts and error/warning handling without real source data."""

import json
from pathlib import Path
import sqlite3

import pytest

from scripts.check_relationships import check_relationships


SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"


@pytest.fixture
def database():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA.read_text(encoding="utf-8"))
    db.executemany(
        "INSERT INTO source_files (file_name,sha256,size_bytes,record_count) VALUES (?,?,1,1)",
        [(name, "a" * 64) for name in
         ["Product.csv", "Storage_Location.csv", "Customer_Order.csv", "Picking_Wave.csv"]],
    )
    db.execute("INSERT INTO products VALUES ('P1','A','PF',1,1)")
    db.execute("INSERT INTO locations VALUES ('L1','1,2,3',1,2,3,2,1)")
    db.execute(
        """INSERT INTO order_records
           (customer_code,order_number,order_to_collect,reference,size_raw,quantity,
            created_at,wave_number,operator_label,source_file_id,source_record_number)
           VALUES ('C1','O1',1,'P1','95',1,'2023-01-05 07:42','W1','OP1',3,1)"""
    )
    add_pick(db, ordinal=1)
    db.commit()
    yield db
    db.close()


def add_pick(db, ordinal, location="L1", wave="W1"):
    db.execute(
        """INSERT INTO picking_records
           (wave_number,reference,size_raw,quantity,location_code,operator_label,
            source_file_id,source_record_number)
           VALUES (?,'P1','9.5',1,?,'OP1',4,?)""", (wave, location, ordinal),
    )


def test_fully_matched_data_has_no_errors_or_warnings(database):
    report = check_relationships(database)
    assert report["status"] == "ok"
    assert report["errors"] == []
    assert report["warnings"] == []
    assert report["row_counts"] == {
        "products": 1, "locations": 1, "order_records": 1, "picking_records": 1,
    }
    assert report["product_coverage"] == {
        "order_records": {"unmatched_records": 0, "unmatched_references": 0},
        "picking_records": {"unmatched_records": 0, "unmatched_references": 0},
    }
    assert report["location_coverage"] == {
        "total_records": 1, "matched_records": 1, "unmatched_records": 0, "unmatched_codes": 0,
    }
    assert report["wave_coverage"] == {
        "order_waves": 1, "picking_waves": 1, "shared_waves": 1,
        "order_only_waves": 0, "picking_only_waves": 0,
    }
    json.dumps(report)  # The build command can serialize this without custom types.


def test_unmatched_locations_are_warnings_and_repeats_count_as_records(database):
    add_pick(database, ordinal=2, location="UNKNOWN")
    add_pick(database, ordinal=3, location="UNKNOWN")
    database.commit()
    report = check_relationships(database)
    assert report["status"] == "warning"
    assert report["errors"] == []
    assert report["warnings"] == ["picking_locations_missing_from_master"]
    assert report["location_coverage"] == {
        "total_records": 3, "matched_records": 1, "unmatched_records": 2, "unmatched_codes": 1,
    }
    assert report["wave_coverage"]["shared_waves"] == 1


def test_distinct_waves_are_not_multiplied_by_repeated_rows(database):
    add_pick(database, ordinal=2)
    add_pick(database, ordinal=3)
    database.execute(
        """INSERT INTO order_records
           (customer_code,order_number,order_to_collect,reference,size_raw,quantity,
            created_at,wave_number,operator_label,source_file_id,source_record_number)
           SELECT customer_code,order_number,order_to_collect,reference,size_raw,quantity,
                  created_at,wave_number,operator_label,source_file_id,2
           FROM order_records WHERE source_record_number=1"""
    )
    database.commit()
    report = check_relationships(database)
    assert report["status"] == "ok"
    assert report["row_counts"]["order_records"] == 2
    assert report["row_counts"]["picking_records"] == 3
    assert report["wave_coverage"]["shared_waves"] == 1


def test_waves_present_on_only_one_side_are_reported_separately(database):
    database.execute("UPDATE order_records SET wave_number='ORDER_ONLY'")
    add_pick(database, ordinal=2, wave="PICK_ONLY")
    database.commit()
    report = check_relationships(database)
    assert report["status"] == "warning"
    assert report["wave_coverage"] == {
        "order_waves": 1, "picking_waves": 2, "shared_waves": 0,
        "order_only_waves": 1, "picking_only_waves": 2,
    }
    assert set(report["warnings"]) == {
        "order_waves_without_picking_records", "picking_waves_without_order_records",
    }


@pytest.mark.parametrize("table", ["order_records", "picking_records"])
def test_missing_product_is_an_error_even_if_enforcement_was_bypassed(database, table):
    database.execute("PRAGMA foreign_keys=OFF")
    database.execute(f"UPDATE {table} SET reference='MISSING'")
    database.commit()
    database.execute("PRAGMA foreign_keys=ON")
    report = check_relationships(database)
    assert report["status"] == "error"
    assert f"{table}_missing_products" in report["errors"]
    assert report["product_coverage"][table] == {
        "unmatched_records": 1, "unmatched_references": 1,
    }
    assert report["foreign_key_violations"]["count"] == 1


def test_orphan_source_link_is_an_error(database):
    database.execute("PRAGMA foreign_keys=OFF")
    database.execute("UPDATE picking_records SET source_file_id=999")
    database.commit()
    database.execute("PRAGMA foreign_keys=ON")
    report = check_relationships(database)
    assert report["status"] == "error"
    assert "foreign_key_violations" in report["errors"]
    assert report["foreign_key_violations"]["examples"][0]["parent"] == "source_files"


def test_disabled_foreign_keys_are_reported_without_changing_setting(database):
    database.execute("PRAGMA foreign_keys=OFF")
    report = check_relationships(database)
    assert report["status"] == "error"
    assert "foreign_keys_disabled" in report["errors"]
    assert database.execute("PRAGMA foreign_keys").fetchone() == (0,)


def test_empty_tables_do_not_appear_to_be_a_successful_load():
    db = sqlite3.connect(":memory:")
    try:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        report = check_relationships(db)
        assert report["status"] == "error"
        assert report["errors"] == ["required_tables_empty"]
        assert len(report["empty_tables"]) == 4
        assert report["location_coverage"]["total_records"] == 0
        assert report["wave_coverage"]["shared_waves"] == 0
    finally:
        db.close()


def test_check_is_read_only_and_preserves_transaction(database):
    database.execute("BEGIN")
    add_pick(database, ordinal=2)
    before = '\n'.join(database.iterdump())
    changes = database.total_changes
    database.execute("PRAGMA query_only=ON")
    report = check_relationships(database)
    assert report["row_counts"]["picking_records"] == 2
    assert database.total_changes == changes
    assert '\n'.join(database.iterdump()) == before
    assert database.in_transaction
    database.rollback()


def test_missing_schema_raises_without_creating_tables():
    db = sqlite3.connect(":memory:")
    try:
        with pytest.raises(sqlite3.OperationalError):
            check_relationships(db)
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    finally:
        db.close()
