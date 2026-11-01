"""Load warehouse locations into a connection initialized with sql/schema.sql.

The caller owns the connection. This module has no command-line entry point.
Coordinate agreement is a data check, not validation of physical units or routes.
"""

import csv
import hashlib
import io
from pathlib import Path
import sqlite3


EXPECTED_HEADERS = ["originalLocation", "position", "x", "y", "z"]


def load_locations(connection: sqlite3.Connection, source_path: Path) -> int:
    """Register and load locations atomically; return inserted record count.

    Preserve shared coordinates and original position text. Require integer
    coordinates that agree with position. Reject duplicates instead of replacing.
    The connection must have the schema and no active transaction.
    """
    if connection.in_transaction:
        raise ValueError("Finish the active transaction before loading locations")

    source_path = Path(source_path)
    # This reference file is about 75 KB. Parse and hash the same byte snapshot.
    source_bytes = source_path.read_bytes()
    reader = csv.reader(
        io.StringIO(source_bytes.decode("utf-8-sig"), newline=""),
        delimiter=",", strict=True,
    )
    if next(reader, None) != EXPECTED_HEADERS:
        raise ValueError(f"Expected location headers: {EXPECTED_HEADERS}")

    locations = []
    for record_number, row in enumerate(reader, start=1):
        if len(row) != len(EXPECTED_HEADERS):
            raise ValueError(f"Location record {record_number}: expected 5 fields")
        if any(not value.strip() for value in row):
            raise ValueError(f"Location record {record_number}: blank required field")
        location_code, position_raw, *coordinate_fields = row
        try:
            coordinates = tuple(int(value) for value in coordinate_fields)
            position_coordinates = tuple(int(value.strip()) for value in position_raw.split(","))
        except ValueError as error:
            raise ValueError(
                f"Location record {record_number}: expected integer coordinates"
            ) from error
        if position_coordinates != coordinates:
            raise ValueError(f"Location record {record_number}: position and x/y/z disagree")
        locations.append((location_code.strip(), position_raw, *coordinates, record_number))
    if not locations:
        raise ValueError("Location file contains no data records")

    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        raise ValueError("Foreign-key enforcement must be enabled")

    connection.execute("BEGIN")
    try:
        cursor = connection.execute(
            """INSERT INTO source_files (file_name, sha256, size_bytes, record_count)
               VALUES (?, ?, ?, ?)""",
            (source_path.name, hashlib.sha256(source_bytes).hexdigest(),
             len(source_bytes), len(locations)),
        )
        source_id = cursor.lastrowid
        connection.executemany(
            """INSERT INTO locations
               (location_code, position_raw, x, y, z, source_file_id, source_record_number)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(code, position, x, y, z, source_id, ordinal)
             for code, position, x, y, z, ordinal in locations],
        )
        loaded_count = connection.execute(
            "SELECT count(*) FROM locations WHERE source_file_id = ?", (source_id,)
        ).fetchone()[0]
        if loaded_count != len(locations):
            raise ValueError("Loaded location count does not match source record count")
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise
    return loaded_count
