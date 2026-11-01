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

-- One original order-detail record. Repeated business attributes are preserved.
-- Orders may span waves/operators; neither is forced into a single order header.
CREATE TABLE order_records (
    order_record_id INTEGER PRIMARY KEY,
    customer_code TEXT NOT NULL
        CHECK (length(customer_code) > 0 AND customer_code = trim(customer_code)),
    order_number TEXT NOT NULL
        CHECK (length(order_number) > 0 AND order_number = trim(order_number)),
    order_to_collect INTEGER NOT NULL CHECK (order_to_collect >= 1),
    reference TEXT NOT NULL REFERENCES products (reference),
    -- Preserve source size text, including empty strings; no size mapping applied.
    size_raw TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    -- Order creation time: YYYY-MM-DD HH:MM, timezone unspecified by source.
    -- Calendar validity is checked by the loader, not by this length constraint.
    created_at TEXT NOT NULL CHECK (length(created_at) = 16),
    wave_number TEXT NOT NULL
        CHECK (length(wave_number) > 0 AND wave_number = trim(wave_number)),
    operator_label TEXT NOT NULL
        CHECK (length(operator_label) > 0 AND operator_label = trim(operator_label)),
    source_file_id INTEGER NOT NULL REFERENCES source_files (source_file_id),
    source_record_number INTEGER NOT NULL CHECK (source_record_number >= 1),
    UNIQUE (source_file_id, source_record_number)
) STRICT;

-- One original picking-assignment record, not a confirmed completed pick.
-- Preserve repeated assignments; wave/product/size/location is not a unique key.
CREATE TABLE picking_records (
    picking_record_id INTEGER PRIMARY KEY,
    wave_number TEXT NOT NULL
        CHECK (length(wave_number) > 0 AND wave_number = trim(wave_number)),
    reference TEXT NOT NULL REFERENCES products (reference),
    size_raw TEXT NOT NULL CHECK (length(trim(size_raw)) > 0),
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    -- No location foreign key: the supplied master is incomplete.
    -- Retain unmatched codes for later coverage checks; never invent master rows.
    location_code TEXT NOT NULL
        CHECK (length(location_code) > 0 AND location_code = trim(location_code)),
    operator_label TEXT NOT NULL
        CHECK (length(operator_label) > 0 AND operator_label = trim(operator_label)),
    source_file_id INTEGER NOT NULL REFERENCES source_files (source_file_id),
    source_record_number INTEGER NOT NULL CHECK (source_record_number >= 1),
    UNIQUE (source_file_id, source_record_number)
) STRICT;

-- Source counts, hash/file correspondence, and record-number bounds are loader checks.
-- No source data is inserted by this schema.
COMMIT;
