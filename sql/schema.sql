-- Initialize a fresh database; rerunning against existing tables is an error.
-- Future connections must also enable foreign_keys before starting a transaction.
PRAGMA foreign_keys = ON;

BEGIN;

-- One registered file per filename in the current source snapshot.
-- sha256 identifies inspected bytes; its format does not prove upstream authenticity.
CREATE TABLE source_files (
    source_file_id INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL UNIQUE
        CHECK (length(file_name) > 0 AND file_name = trim(file_name)),
    sha256 TEXT NOT NULL
        CHECK (length(sha256) = 64 AND sha256 NOT GLOB '*[^0-9a-f]*'),
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    record_count INTEGER NOT NULL CHECK (record_count >= 0)
) STRICT;

-- One reference-level product, not one product/size variant.
-- The future loader will trim derived reference/class/sector values and retain raw files.
CREATE TABLE products (
    reference TEXT NOT NULL PRIMARY KEY
        CHECK (length(reference) > 0 AND reference = trim(reference)),
    abc_code TEXT NOT NULL CHECK (abc_code IN ('A', 'B', 'C')),
    sector TEXT NOT NULL
        CHECK (length(sector) > 0 AND sector = trim(sector)),
    source_file_id INTEGER NOT NULL REFERENCES source_files (source_file_id),
    -- Parsed data-record ordinal, starting at 1 after the header, not physical line.
    source_record_number INTEGER NOT NULL CHECK (source_record_number >= 1),
    UNIQUE (source_file_id, source_record_number)
) STRICT;

-- One named location; different codes may legitimately share coordinates.
-- position_raw retains the original coordinate string from the source.
CREATE TABLE locations (
    location_code TEXT NOT NULL PRIMARY KEY
        CHECK (length(location_code) > 0 AND location_code = trim(location_code)),
    position_raw TEXT NOT NULL CHECK (length(trim(position_raw)) > 0),
    x INTEGER NOT NULL,
    y INTEGER NOT NULL,
    z INTEGER NOT NULL,
    source_file_id INTEGER NOT NULL REFERENCES source_files (source_file_id),
    source_record_number INTEGER NOT NULL CHECK (source_record_number >= 1),
    UNIQUE (source_file_id, source_record_number)
) STRICT;

-- Source counts, hash/file correspondence, and record-number bounds are loader checks.
-- No source data is inserted by this schema.
COMMIT;
