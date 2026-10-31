"""Print a read-only inventory of the top-level source CSVs as JSON.

Run from any directory: python scripts/inspect_sources.py [source_directory]
Only comma and semicolon delimiters and UTF-8 (with optional BOM) are supported.
"""

import argparse
import csv
import json
from pathlib import Path


DEFAULT_SOURCE_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def inspect_csv(path: Path) -> dict:
    """Stream one CSV; count all records but profile blanks only in valid-width rows.

    A record is a parsed CSV row, not necessarily one physical line. Completely
    empty rows count as malformed records. Whitespace-only cells count as blank.
    Invalid headers or CSV syntax raise ValueError; source values are never edited.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        # These sources have simple, single-line headers. Infer from the header
        # only so embedded semicolons in quoted storage cells cannot decide it.
        header_line = handle.readline()
        if not header_line.strip():
            raise ValueError("Missing or blank header")
        dialect = csv.Sniffer().sniff(header_line, delimiters=",;")
        handle.seek(0)
        reader = csv.reader(handle, delimiter=dialect.delimiter, strict=True)
        headers = next(reader)
        if any(not name.strip() for name in headers):
            raise ValueError("Blank column name")
        if len(set(headers)) != len(headers):
            raise ValueError("Duplicate column names")

        record_count = 0
        malformed_count = 0
        blank_counts = dict.fromkeys(headers, 0)
        for row in reader:
            record_count += 1
            if len(row) != len(headers):
                malformed_count += 1
                continue
            for name, value in zip(headers, row):
                if not value.strip():
                    blank_counts[name] += 1

    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "delimiter": dialect.delimiter,
        "headers": headers,
        "record_count": record_count,
        "valid_width_record_count": record_count - malformed_count,
        "malformed_width_record_count": malformed_count,
        "blank_fields_in_valid_width_records": blank_counts,
    }


def main(argv=None) -> int:
    """Print one report per CSV; return 1 for read/parse/width errors, else 0."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_directory", nargs="?", type=Path,
                        default=DEFAULT_SOURCE_DIR)
    args = parser.parse_args(argv)
    source_dir = args.source_directory
    if not source_dir.is_dir():
        parser.error(f"Source directory does not exist: {source_dir}")
    paths = sorted(path for path in source_dir.iterdir()
                   if path.is_file() and path.suffix.lower() == ".csv")
    if not paths:
        parser.error(f"No top-level CSV files found: {source_dir}")

    failed = False
    for path in paths:
        try:
            report = inspect_csv(path)
            failed = failed or report["malformed_width_record_count"] > 0
        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            report = {"file": path.name, "error": str(error)}
            failed = True
        print(json.dumps(report, ensure_ascii=True))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
