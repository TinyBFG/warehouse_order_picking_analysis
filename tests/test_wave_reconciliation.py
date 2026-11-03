"""Check the actual analytical SQL against small, independently specified cases.

The query needs only wave_number and quantity. Minimal in-memory tables isolate
its logic from ingestion; loader/schema behavior is covered by separate tests.
"""

from pathlib import Path
import sqlite3

import pytest


QUERY = (Path(__file__).resolve().parents[1] / "sql" / "wave_reconciliation.sql").read_text(
    encoding="utf-8"
)
OUTPUT_COLUMNS = [
    "shared_wave_count", "equal_quantity_wave_count", "unequal_quantity_wave_count",
    "reconciliation_rate_pct", "order_only_wave_count", "picking_only_wave_count",
]


@pytest.mark.parametrize("orders,picks,expected", [
    ([], [], (0, 0, 0, None, 0, 0)),
    ([("A", 0)], [], (0, 0, 0, None, 1, 0)),
    ([], [("A", 0)], (0, 0, 0, None, 0, 1)),
    ([("A", 2)], [("B", 2)], (0, 0, 0, None, 1, 1)),
    ([("A", 2)], [("A", 2)], (1, 1, 0, 100.0, 0, 0)),
    ([("A", 2)], [("A", 1)], (1, 0, 1, 0.0, 0, 0)),
    ([("A", 2), ("B", 3), ("ORDER_ONLY", 100)],
     [("A", 2), ("B", 1), ("PICK_ONLY", 100)], (2, 1, 1, 50.0, 1, 1)),
    ([("A", 1), ("A", 1)], [("A", 1)], (1, 0, 1, 0.0, 0, 0)),
    ([("A", 2)], [("A", 1), ("A", 1)], (1, 1, 0, 100.0, 0, 0)),
    ([("A", 0)], [("A", 0)], (1, 1, 0, 100.0, 0, 0)),
    ([("001", 1)], [("1", 1)], (0, 0, 0, None, 1, 1)),
    ([("wave", 1)], [("WAVE", 1)], (0, 0, 0, None, 1, 1)),
    ([("LARGE", 1000), ("SMALL", 1)],
     [("LARGE", 1000), ("SMALL", 2)], (2, 1, 1, 50.0, 0, 0)),
    ([("SHARED", 0), ("ORDER_ONLY", 0)],
     [("SHARED", 0), ("PICK_ONLY", 0)], (1, 1, 0, 100.0, 1, 1)),
], ids=[
    "both_empty", "order_only_zero", "picking_only_zero", "disjoint_waves",
    "equal", "unequal", "half_equal_with_coverage_gaps", "repeated_orders",
    "repeated_picks_equal_units", "shared_zero", "leading_zeros", "case_sensitive",
    "wave_weighted_not_unit_weighted", "zero_totals_still_establish_presence",
])
def test_wave_reconciliation_contract(orders, picks, expected):
    db = sqlite3.connect(":memory:")
    try:
        db.executescript(
            "CREATE TABLE order_records (wave_number TEXT NOT NULL, quantity INTEGER NOT NULL);"
            "CREATE TABLE picking_records (wave_number TEXT NOT NULL, quantity INTEGER NOT NULL);"
        )
        db.executemany("INSERT INTO order_records VALUES (?, ?)", orders)
        db.executemany("INSERT INTO picking_records VALUES (?, ?)", picks)
        before = db.total_changes
        db.execute("PRAGMA query_only = ON")
        cursor = db.execute(QUERY)
        assert [column[0] for column in cursor.description] == OUTPUT_COLUMNS
        result = cursor.fetchone()
        assert cursor.fetchone() is None  # Exactly one summary row, even if inputs are empty.
        for actual, wanted in zip(result, expected):
            if wanted is None:
                assert actual is None
            elif isinstance(wanted, float):
                assert actual == pytest.approx(wanted)
            else:
                assert actual == wanted
        assert db.total_changes == before
        assert result[1] + result[2] == result[0]
        assert result[0] + result[4] == len({wave for wave, _ in orders})
        assert result[0] + result[5] == len({wave for wave, _ in picks})
    finally:
        db.close()
