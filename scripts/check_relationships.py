"""Read-only relationship checks for the four loaded warehouse datasets.

Known coverage gaps are warnings, not evidence of unfulfilled demand or failed
picks. No size mapping, quantity reconciliation, or analytical KPIs are calculated.
This module provides a function for a later database-build command.
"""

import sqlite3


def check_relationships(connection: sqlite3.Connection) -> dict:
    """Return JSON-compatible counts, errors, warnings, and an overall status.

    Requires the project schema. All four data tables must contain records for a
    complete check; otherwise report an error rather than imply an empty load is
    valid. Status is error, warning, or ok. Warning status means enforced checks
    passed but coverage gaps remain. Counts are observations, not hardcoded audit
    expectations. Never modify data, settings, or transactions. The caller owns
    the connection and controls its read snapshot if concurrent writes are possible.
    """
    errors = []
    warnings = []
    # Identifiers below are fixed project table names, not external SQL input.
    row_counts = {
        table: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in ("products", "locations", "order_records", "picking_records")
    }
    empty_tables = [table for table, count in row_counts.items() if count == 0]
    if empty_tables:
        errors.append("required_tables_empty")

    foreign_keys_enabled = bool(connection.execute("PRAGMA foreign_keys").fetchone()[0])
    if not foreign_keys_enabled:
        errors.append("foreign_keys_disabled")
    violation_count = 0
    violation_examples = []
    for table, row_id, parent, constraint_id in connection.execute("PRAGMA foreign_key_check"):
        violation_count += 1
        if len(violation_examples) < 10:
            violation_examples.append({
                "table": table, "row_id": row_id, "parent": parent,
                "constraint_id": constraint_id,
            })
    if violation_count:
        errors.append("foreign_key_violations")

    product_coverage = {}
    for table in ("order_records", "picking_records"):
        unmatched_records, unmatched_references = connection.execute(
            f"""SELECT count(*), count(DISTINCT r.reference)
                FROM {table} AS r
                LEFT JOIN products AS p ON r.reference = p.reference
                WHERE p.reference IS NULL"""
        ).fetchone()
        product_coverage[table] = {
            "unmatched_records": unmatched_records,
            "unmatched_references": unmatched_references,
        }
        if unmatched_records:
            errors.append(f"{table}_missing_products")

    total, matched, unmatched_codes = connection.execute(
        """SELECT count(*), count(l.location_code),
                  count(DISTINCT CASE WHEN l.location_code IS NULL
                                     THEN p.location_code END)
           FROM picking_records AS p
           LEFT JOIN locations AS l ON p.location_code = l.location_code"""
    ).fetchone()
    location_coverage = {
        "total_records": total, "matched_records": matched,
        "unmatched_records": total - matched, "unmatched_codes": unmatched_codes,
    }
    if total != matched:
        warnings.append("picking_locations_missing_from_master")

    # Deduplicate wave identifiers before joining: many records share each wave.
    order_waves, picking_waves, shared_waves = connection.execute(
        """WITH order_waves AS (
               SELECT DISTINCT wave_number FROM order_records
           ), picking_waves AS (
               SELECT DISTINCT wave_number FROM picking_records
           )
           SELECT (SELECT count(*) FROM order_waves),
                  (SELECT count(*) FROM picking_waves),
                  (SELECT count(*) FROM order_waves AS o
                   JOIN picking_waves AS p ON o.wave_number = p.wave_number)"""
    ).fetchone()
    wave_coverage = {
        "order_waves": order_waves, "picking_waves": picking_waves,
        "shared_waves": shared_waves,
        "order_only_waves": order_waves - shared_waves,
        "picking_only_waves": picking_waves - shared_waves,
    }
    if wave_coverage["order_only_waves"]:
        warnings.append("order_waves_without_picking_records")
    if wave_coverage["picking_only_waves"]:
        warnings.append("picking_waves_without_order_records")

    return {
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "errors": errors, "warnings": warnings,
        "row_counts": row_counts, "empty_tables": empty_tables,
        "foreign_keys_enabled": foreign_keys_enabled,
        "foreign_key_violations": {
            "count": violation_count, "examples": violation_examples,
        },
        "product_coverage": product_coverage,
        "location_coverage": location_coverage,
        "wave_coverage": wave_coverage,
    }
