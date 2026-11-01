"""Build a validated database: python -B -m scripts.build_database [--replace]."""

import argparse
import csv
import json
from pathlib import Path
import sqlite3
import tempfile

from scripts.check_relationships import check_relationships
from scripts.load_locations import load_locations
from scripts.load_orders import load_orders
from scripts.load_picks import load_picks
from scripts.load_products import load_products


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_DATABASE = PROJECT_ROOT / "data" / "warehouse.sqlite"
SCHEMA = PROJECT_ROOT / "sql" / "schema.sql"
LOADERS = (
    ("Product.csv", load_products),
    ("Storage_Location.csv", load_locations),
    ("Customer_Order.csv", load_orders),
    ("Picking_Wave.csv", load_picks),
)


def _check_destination(path: Path, replace: bool) -> None:
    """Refuse accidental overwrite and replacement with SQLite sidecars present."""
    if path.exists() and not path.is_file():
        raise ValueError(f"Database destination is not a file: {path}")
    if path.exists() and not replace:
        raise FileExistsError(f"Database already exists: {path}. Use --replace to rebuild.")
    for suffix in ("-wal", "-shm", "-journal"):
        if path.with_name(path.name + suffix).exists():
            raise ValueError(f"SQLite companion file exists; close database users first: {path}{suffix}")


def build_database(source_directory=DEFAULT_SOURCE_DIR, database_path=DEFAULT_DATABASE,
                   *, replace: bool = False) -> dict:
    """Build from scratch and return a JSON-compatible validation report.

    Validated on Windows. Never append to an existing database. An explicit
    replace rebuilds separately before replacing the old file; failure preserves
    the old database. Temporary files are removed on normal success or failure.
    Inputs are read only. Keep other database users closed during replacement.
    """
    source_directory = Path(source_directory).resolve()
    requested_path = Path(database_path)
    if requested_path.is_symlink():
        raise ValueError("Database destination must not be a symbolic link")
    database_path = requested_path.resolve()
    for raw_directory in (source_directory, DEFAULT_SOURCE_DIR.resolve()):
        if database_path.is_relative_to(raw_directory):
            raise ValueError("Database destination must be outside raw source directories")
    if database_path.suffix.lower() not in (".sqlite", ".sqlite3", ".db"):
        raise ValueError("Database destination must end in .sqlite, .sqlite3, or .db")
    _check_destination(database_path, replace)
    for filename, _ in LOADERS:
        if not (source_directory / filename).is_file():
            raise FileNotFoundError(f"Required source file missing: {source_directory / filename}")
    schema_sql = SCHEMA.read_text(encoding="utf-8")
    database_path.parent.mkdir(parents=True, exist_ok=True)

    # Same-parent staging avoids an extra database copy and stays on one volume.
    with tempfile.TemporaryDirectory(prefix="warehouse-build-", dir=database_path.parent) as folder:
        staged_path = Path(folder) / "warehouse.sqlite"
        connection = sqlite3.connect(staged_path)
        try:
            connection.executescript(schema_sql)
            loaded_records = {
                filename: loader(connection, source_directory / filename)
                for filename, loader in LOADERS
            }
            checks = check_relationships(connection)
            if checks["status"] == "error":
                raise ValueError("Relationship checks failed: " + ", ".join(checks["errors"]))
            if connection.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite integrity check failed")
            source_files = [
                dict(zip(("file_name", "sha256", "size_bytes", "record_count"), row))
                for row in connection.execute(
                    "SELECT file_name,sha256,size_bytes,record_count FROM source_files ORDER BY file_name"
                )
            ]
        finally:
            connection.close()
        # Recheck after building. On Windows, rename also refuses a destination
        # created by another process between this check and the move.
        _check_destination(database_path, replace)
        if replace:
            staged_path.replace(database_path)
        else:
            staged_path.rename(database_path)

    return {
        "database_path": str(database_path), "loaded_records": loaded_records,
        "integrity_check": "ok", "relationship_checks": checks,
        "source_files": source_files,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--replace", action="store_true",
                        help="Replace the existing database only after a fresh build passes checks")
    args = parser.parse_args(argv)
    try:
        report = build_database(args.source_dir, args.database, replace=args.replace)
    except (OSError, ValueError, UnicodeError, csv.Error, sqlite3.Error) as error:
        parser.exit(1, f"Build failed: {error}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
