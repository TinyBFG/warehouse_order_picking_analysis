"""Load a product CSV into a connection initialized with sql/schema.sql.

This module provides a function, not a command-line database builder. The caller
owns the connection. Raw files are read only; loading never deduplicates or replaces.
"""

import csv
import hashlib
import io
from pathlib import Path
import sqlite3


EXPECTED_HEADERS = ["Reference", "ABCCOD", "Sector"]


def load_products(connection: sqlite3.Connection, source_path: Path) -> int:
    """Atomically register and load one product file; return inserted row count.

    Requires the existing schema and no active transaction. Repeated filenames,
    duplicate references, and invalid product values raise errors rather than
    overwrite existing data. Source ordinals start at 1 after the header.
    """
    if connection.in_transaction:
        raise ValueError("Finish the active transaction before loading products")

    source_path = Path(source_path)
    # Product.csv is a small reference file (about 4 KB). One byte snapshot keeps
    # parsing, byte count, and checksum tied to exactly the same input.
    source_bytes = source_path.read_bytes()
    reader = csv.reader(
        io.StringIO(source_bytes.decode("utf-8-sig"), newline=""),
        delimiter=";", strict=True,
    )
    if next(reader, None) != EXPECTED_HEADERS:
        raise ValueError(f"Expected product headers: {EXPECTED_HEADERS}")

    products = []
    for record_number, row in enumerate(reader, start=1):
        if len(row) != len(EXPECTED_HEADERS):
            raise ValueError(f"Product record {record_number}: expected 3 fields")
        values = [value.strip() for value in row]
        if any(not value for value in values):
            raise ValueError(f"Product record {record_number}: blank required field")
        products.append((*values, record_number))
    if not products:
        raise ValueError("Product file contains no data records")

    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise ValueError("Foreign-key enforcement must be enabled")

    connection.execute("BEGIN")
    try:
        cursor = connection.execute(
            """INSERT INTO source_files (file_name, sha256, size_bytes, record_count)
               VALUES (?, ?, ?, ?)""",
            (source_path.name, hashlib.sha256(source_bytes).hexdigest(),
             len(source_bytes), len(products)),
        )
        source_id = cursor.lastrowid
        connection.executemany(
            """INSERT INTO products
               (reference, abc_code, sector, source_file_id, source_record_number)
               VALUES (?, ?, ?, ?, ?)""",
            [(reference, abc_code, sector, source_id, ordinal)
             for reference, abc_code, sector, ordinal in products],
        )
        loaded_count = connection.execute(
            "SELECT count(*) FROM products WHERE source_file_id = ?", (source_id,)
        ).fetchone()[0]
        if loaded_count != len(products):
            raise ValueError("Loaded product count does not match source record count")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return loaded_count
