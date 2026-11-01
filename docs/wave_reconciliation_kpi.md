# Wave quantity reconciliation KPI

Defined: November 1, 2026. Contract version: 1. Status: proposed for owner review before analytical SQL implementation. No analytical query, dashboard metric, or operational target is implemented by this document.

## Business question and intended use

Among waves represented in both order and picking records, what percentage have equal total recorded ordered units and recorded assigned picking units?

This is a diagnostic of aggregate agreement between two supplied files. It helps identify waves needing investigation. It is not an order fulfillment rate, picking completion rate, inventory accuracy measure, employee performance metric, or causal measure of warehouse efficiency. No external benchmark or performance target has been established.

Display name: **Wave quantity reconciliation rate (%)**.

## Sources and comparison grain

| Table | Fields used | Source meaning |
| --- | --- | --- |
| `order_records` | `wave_number`, `quantity` | Recorded order-detail units assigned to a wave |
| `picking_records` | `wave_number`, `quantity` | Recorded picking-assignment units associated with a wave |

The calculation does not require product, location, operator, customer, or size joins. Raw table grain remains one source record. The comparison grain must be **one row per wave on each side before joining**.

Wave identifiers are the loader's trimmed text values. Preserve their case and leading zeros; do not cast them to integers to force matches. There is no verified order-line-to-picking-record key.

The initial scope is the complete four-file database snapshot produced by the build command. See [setup instructions](development_setup.md), [source dictionary](source_data_dictionary.md), and [provenance limits](source_provenance.md).

## Formula

For each wave:

- Order units = sum of `order_records.quantity` for that wave.
- Picking units = sum of `picking_records.quantity` for that wave.
- A shared wave has at least one record in each table, regardless of its total quantity.
- An equal-quantity wave is a shared wave whose two integer totals are exactly equal.

**Numerator:** count of equal-quantity shared waves.

**Denominator:** count of all shared waves.

**Rate (%):** `100 x numerator / denominator`.

The output unit is percent on a 0 to 100 scale; each wave contributes one vote regardless of its size. This is a wave-weighted rate, not a unit-weighted rate. Use decimal division rather than integer truncation. Preserve precision during calculation and round to two decimal places only for display.

If there are no shared waves, return a missing numeric result (SQL `NULL` / display `N/A`), not 0% or 100%. The absence of comparable waves is not evidence of agreement or disagreement.

## Inclusion and exclusion rules

| Condition | Contract rule | Reason |
| --- | --- | --- |
| Repeated source records | Retain and sum all quantities. | Repeated assignments may represent separate units; no deduplication rule is approved. |
| Zero-quantity records | Retain; zero contributes zero units and still establishes wave presence. | A zero total is different from an absent wave. |
| Blank order sizes | Retain. | Size is not part of this comparison grain. |
| Differently encoded sizes | Do not normalize or compare size values in this KPI. | Wave totals do not require a size-level mapping. |
| Picking locations absent from the master | Retain. | Joining to the location master would incorrectly remove assignment units. |
| Different operator labels or multiple operators per wave | Retain all records; do not filter or join on operator. | Operator assignments are not a verified cross-file matching key. |
| Wave present only in orders | Exclude from this rate's numerator and denominator; report separately. | There is no picking total to compare. Do not replace absence with zero. |
| Wave present only in picking | Exclude from this rate's numerator and denominator; report separately. | There is no order total to compare. |
| Blank/malformed wave identifiers, invalid quantities, or broken enforced relationships | Stop publication and investigate the failed validation. | Do not silently drop invalid records to improve the metric. |

All source records in the loaded snapshot are included unless explicitly excluded above. Do not filter by creation date, operator, product, customer, or location in version 1. Picking records have no verified execution timestamp, and an order-date filter can remove only part of a wave. Any segmented metric needs its own approved scope and denominator rules.

## Required reporting outputs

The main output is one summary row for the full snapshot:

| Output field | Definition | Output type |
| --- | --- | --- |
| `shared_wave_count` | Waves present in both tables | Nonnegative integer |
| `equal_quantity_wave_count` | Shared waves with exactly equal totals | Nonnegative integer |
| `unequal_quantity_wave_count` | Shared waves with unequal totals | Nonnegative integer |
| `reconciliation_rate_pct` | Defined percentage, or missing if no shared waves | Numeric or NULL; no percent-sign text in exports |
| `order_only_wave_count` | Distinct order waves absent from picking | Nonnegative integer |
| `picking_only_wave_count` | Distinct picking waves absent from orders | Nonnegative integer |

Always display both one-sided coverage counts beside the rate. They are necessary context, even though they are not part of its denominator. A complete implementation may use multiple short queries instead of one complicated query.

Retain auditable wave-level comparison results for checking the calculation: shared wave identifier, order units, picking units, signed difference (`order units - picking units`), and equal/unequal classification. Each shared wave must occur once. One-sided wave identifiers can be inspected separately without inventing missing totals.

Record the contract version, source file checksums, and snapshot scope alongside any eventual exported results. The database's `source_files` table supplies file metadata; a successful rebuild alone does not identify an external dataset version.

## Independently calculated baseline

The following baseline was calculated directly from the CSVs using Python integer sums keyed by wave, then checked against the saved SQLite records. No business analytical SQL solution was authored. The database's stored file checksums and byte counts matched the local source files during verification.

| Quantity | Current snapshot result |
| --- | ---: |
| Distinct order waves | 9,784 |
| Distinct picking waves | 9,707 |
| Shared waves (denominator) | 9,707 |
| Equal-quantity shared waves (numerator) | 7,394 |
| Unequal-quantity shared waves | 2,313 |
| Order-only waves | 77 |
| Picking-only waves | 0 |
| Reconciliation rate, displayed | 76.17% |

The unrounded baseline is approximately 76.1718347584%. All 2,313 unequal shared waves currently have more order units than picking units. This describes the supplied records; it does not explain the reason for the difference.

Source totals remain 122,370 order records containing 228,195 units, and 215,192 picking records containing 215,192 units. Summed row counts are not substitutes for summed units.

## Actual examples for checking later SQL

| Wave | Order records | Order units | Picking records | Picking units | KPI treatment |
| --- | ---: | ---: | ---: | ---: | --- |
| `33169` | 21 | 24 | 24 | 24 | Shared and equal; contributes to numerator and denominator |
| `33170` | 21 | 24 | 23 | 23 | Shared and unequal; contributes only to denominator |
| `33178` | 17 | 21 | 17 | 17 | Shared and unequal despite equal record counts |
| `33219` | 1 | 2 | 0 | Not available | Order-only; excluded from rate and reported as a coverage gap |

Wave `33169` demonstrates why `SUM(quantity)` is necessary. Wave `33178` demonstrates why matching `COUNT(*)` values cannot establish quantity agreement.

## Validation requirements for the later query

1. Confirm a successful database build with no enforced relationship errors. Known location and wave coverage warnings remain visible rather than being filtered away.
2. Aggregate each side independently. Do not join raw records on wave number: a wave with three order rows and four picking rows can produce twelve joined rows, inflating quantities.
3. Confirm each wave aggregate has a unique wave identifier and that all-wave aggregated units reconcile to each source table's total units before selecting shared waves.
4. Compare the later SQL numerator, denominator, and one-sided counts with the independent baseline and actual examples above.
5. Verify `equal count + unequal count = shared count`, `shared count + order-only count = distinct order waves`, and `shared count + picking-only count = distinct picking waves`.
6. Verify the numerator never exceeds the denominator and a nonmissing rate lies between 0 and 100.
7. Check these small edge cases independently before publishing results:
   - One equal and one unequal shared wave yields 50%.
   - Adding an order-only wave leaves that 50% unchanged but increases the order-only coverage count.
   - Waves present on both sides with total zero are comparable and equal.
   - A zero-total wave present on only one side is still one-sided, not an equal wave.
   - No shared waves yields a missing rate, including when either side is empty.
   - Repeated records contribute their recorded quantities; zero quantities do not disappear from wave presence.
8. A missing-rate edge case describes the formula's behavior. The full database build separately rejects empty required tables; these are different checks.

## Interpretation limits and next review

Equal aggregate quantities do not prove equal product or size composition: differences within a wave may cancel. This metric cannot establish completed work, fulfillment, employee output, or the cause of discrepancies. File extraction scope, timing, transformations, and uncertain provenance remain material limitations.

A higher aggregate agreement rate alone does not establish better warehouse performance. Do not set an operational target or recommend staffing/storage changes from this metric alone.

After owner review, the next separate task is for the project author to attempt the analytical SQL. The query must then be reviewed and validated against this contract. This document does not approve automatic continuation to that task.
