"""Load order source records without deduplication or size normalization.

Use load_orders(connection, source_path) after initializing sql/schema.sql and
loading products. No database builder or command-line entry point is provided.
"""

import csv
from datetime import datetime
import hashlib
import io
from pathlib import Path
import sqlite3


EXPECTED_HEADERS = [
    "codCustomer", "orderNumber", "orderToCollect", "Reference", "Size (US)",
    "quantity (units)", "creationDate", "waveNumber", "operator",
]


def load_orders(connection: sqlite3.Connection, source_path: Path) -> int:
    """Atomically load original order records and metadata; return record count.

    Requires the existing schema, registered products, and no active transaction.
    Read one byte snapshot for consistent parsing/checksum; insert parsed records
    individually without keeping a second list of all parsed rows. Blank size text,
    zero quantities, and repeated business records are preserved. Unknown products
    fail the foreign-key constraint. Errors roll back this entire load.
    """
    if connection.in_transaction:
        raise ValueError("Finish the active transaction before loading orders")
    source_path = Path(source_path)
    source_bytes = source_path.read_bytes()
    reader = csv.reader(
        io.StringIO(source_bytes.decode("utf-8-sig"), newline=""),
        delimiter=";", strict=True,
    )
    if next(reader, None) != EXPECTED_HEADERS:
        raise ValueError(f"Expected order headers: {EXPECTED_HEADERS}")

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
                raise ValueError(f"Order record {record_count}: expected 9 fields")
            values = [value.strip() for value in row]
            if any(not value for index, value in enumerate(values) if index != 4):
                raise ValueError(f"Order record {record_count}: blank required field")
            customer, order, sequence, reference, _, quantity, created, wave, operator = values
            try:
                sequence = int(sequence)
                quantity = int(quantity)
                created_at = datetime.strptime(created, "%d/%m/%Y %H:%M").strftime(
                    "%Y-%m-%d %H:%M"
                )
            except ValueError as error:
                raise ValueError(
                    f"Order record {record_count}: invalid integer or creation timestamp"
                ) from error
            if sequence < 1 or quantity < 0:
                raise ValueError(f"Order record {record_count}: invalid sequence or quantity")
            connection.execute(
                """INSERT INTO order_records
                   (customer_code, order_number, order_to_collect, reference, size_raw,
                    quantity, created_at, wave_number, operator_label,
                    source_file_id, source_record_number)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (customer, order, sequence, reference, row[4], quantity, created_at,
                 wave, operator, source_id, record_count),
            )
            source_units += quantity
        if record_count == 0:
            raise ValueError("Order file contains no data records")
        loaded = connection.execute(
            """SELECT count(*), sum(quantity) FROM order_records
               WHERE source_file_id = ?""", (source_id,),
        ).fetchone()
        if loaded != (record_count, source_units):
            raise ValueError("Loaded order counts or quantities do not match the source")
        connection.execute(
            "UPDATE source_files SET record_count = ? WHERE source_file_id = ?",
            (record_count, source_id),
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return record_count
