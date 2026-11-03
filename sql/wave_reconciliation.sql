-- Analyst-authored query developed through the Task 16 exercises and review.
-- Contract: docs/wave_reconciliation_kpi.md, version 1.
-- Full snapshot; preserve repeated records and zero quantities. No size mapping.
-- Compare totals before joining. One-sided waves are reported outside the rate.
WITH order_totals AS (
    SELECT wave_number, SUM(quantity) AS order_units
    FROM order_records
    GROUP BY wave_number
),
picking_totals AS (
    SELECT wave_number, SUM(quantity) AS picking_units
    FROM picking_records
    GROUP BY wave_number
),
wave_comparison AS (
    SELECT
        o.wave_number,
        o.order_units,
        p.picking_units,
        o.order_units - p.picking_units AS unit_difference,
        CASE
            WHEN o.order_units = p.picking_units THEN 'equal'
            ELSE 'unequal'
        END AS comparison_status
    FROM order_totals AS o
    INNER JOIN picking_totals AS p
        ON o.wave_number = p.wave_number
),
wave_summary AS (
    SELECT
        COUNT(*) AS shared_wave_count,
        COALESCE(
            SUM(CASE WHEN comparison_status = 'equal' THEN 1 ELSE 0 END),
            0
        ) AS equal_quantity_wave_count,
        COALESCE(
            SUM(CASE WHEN comparison_status = 'unequal' THEN 1 ELSE 0 END),
            0
        ) AS unequal_quantity_wave_count
    FROM wave_comparison
),
order_only AS (
    SELECT order_totals.wave_number, order_units
    FROM order_totals
    LEFT JOIN picking_totals
        ON order_totals.wave_number = picking_totals.wave_number
    WHERE picking_totals.wave_number IS NULL
),
picking_only AS (
    SELECT picking_totals.wave_number, picking_units
    FROM picking_totals
    LEFT JOIN order_totals
        ON picking_totals.wave_number = order_totals.wave_number
    WHERE order_totals.wave_number IS NULL
)
SELECT
    shared_wave_count,
    equal_quantity_wave_count,
    unequal_quantity_wave_count,
    100.0 * equal_quantity_wave_count / NULLIF(shared_wave_count, 0)
        AS reconciliation_rate_pct,
    (SELECT COUNT(*) FROM order_only) AS order_only_wave_count,
    (SELECT COUNT(*) FROM picking_only) AS picking_only_wave_count
FROM wave_summary;
