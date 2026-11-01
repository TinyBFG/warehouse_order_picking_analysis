"""Load picking assignments without deduplication or size normalization.

Use load_picks(connection, source_path) after initializing sql/schema.sql and
loading products. Locations and orders need not already be loaded. This function
preserves unmatched location codes; it does not confirm picking completion.
No command-line database builder is provided.
"""

import csv
import hashlib
import io
from pathlib import Path
import sqlite3


EXPECTED_HEADERS = [
    "waveNumber", "reference", "Size (US)", "quantityToPick (units)",
    "locations", "operator",
]


def load_picks(connection: sqlite3.Connection, source_path: Path) -> int:
    """Atomically load picking records and metadata; return inserted row count.

    Require the schema, registered products, and no active transaction. Parse and
    hash the same byte snapshot, inserting rows individually. Preserve size text,
    repeated records, and all nonnegative quantities, including zero. Trim derived
    identifiers only. Repeat loads and invalid records fail without partial data.
    """
    if connection.in_transaction:
        raise ValueError("Finish the active transaction before loading picking records")
    source_path = Path(source_path)
    source_bytes = source_path.read_bytes()
    reader = csv.reader(
        io.StringIO(source_bytes.decode("utf-8-sig"), newline=""),
        delimiter=";", strict=True,
    )
    if next(reader, None) != EXPECTED_HEADERS:
        raise ValueError(f"Expected picking headers: {EXPECTED_HEADERS}")

    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise ValueError("Foreign-key enforcement must be enabled")

    connection.execute("BEGIN")
    try:
        cursor = connection.execute(
            """INSERT INTO source_files (file_name, sha256, size_bytes, record_count)
               VALUES (?, ?, ?, 0)""",
            (source_path.name, hashlib.sha256(source_bytes).hexdigest(), len(source_bytes)),
        )
        source_id = cursor.lastrowid
        record_count = 0
        source_units = 0
        for record_count, row in enumerate(reader, start=1):
            if len(row) != len(EXPECTED_HEADERS):
                raise ValueError(f"Picking record {record_count}: expected 6 fields")
            values = [value.strip() for value in row]
            if any(not value for value in values):
                raise ValueError(f"Picking record {record_count}: blank required field")
            wave, reference, _, quantity, location, operator = values
            try:
                quantity = int(quantity)
            except ValueError as error:
                raise ValueError(
                    f"Picking record {record_count}: expected integer quantity"
                ) from error
            if quantity < 0:
                raise ValueError(f"Picking record {record_count}: negative quantity")
            connection.execute(
                """INSERT INTO picking_records
                   (wave_number, reference, size_raw, quantity, location_code,
                    operator_label, source_file_id, source_record_number)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (wave, reference, row[2], quantity, location, operator, source_id, record_count),
            )
            source_units += quantity
        if record_count == 0:
            raise ValueError("Picking file contains no data records")
        loaded = connection.execute(
            """SELECT count(*), sum(quantity) FROM picking_records
               WHERE source_file_id = ?""", (source_id,),
        ).fetchone()
        if loaded != (record_count, source_units):
            raise ValueError("Loaded picking counts or quantities do not match the source")
        connection.execute(
            "UPDATE source_files SET record_count = ? WHERE source_file_id = ?",
            (record_count, source_id),
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return record_count
