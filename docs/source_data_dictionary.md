# Source data dictionary and grain contracts

Reviewed: October 30, 2026. This document describes the nine CSVs currently in `data/raw/`. It is a source contract for future loaders and analysis, not an implemented SQLite schema. Counts describe this local snapshot, not permanent expectations for every future download.

For acquisition, licensing, and generation-method uncertainties, see [source provenance](source_provenance.md). Meanings attributed to the source refer to `data/raw/README.txt`; an observed pattern is not proof of operational meaning.

## Shared rules

- Grain means what one row represents. Distinguish the observable source-record grain from the business event the record may describe.
- Read CSV values as text initially, using UTF-8 with optional BOM and the actual delimiter. Preserve identifiers, leading zeros, case, and raw size strings.
- Source records remain immutable. Proposed trimming, parsing, or renaming happens only in derived fields and must be tested before loading.
- Preserve repeated records. No verified natural record key exists for orders or picking. A future generated record ID and source filename plus parsed record ordinal can provide technical identity; neither proves business-event uniqueness. A parsed record ordinal is not necessarily a physical line number.
- Proposed types below are future validation targets, not database constraints already enforced. Blank sizes must be retained and classified explicitly rather than replaced with zero. Other parse failures must be surfaced rather than silently coerced.
- Do not treat all populated fields as valid. Keys, domains, relationships, quantities, and business meanings need separate checks.

## Source overview

| File | Delimiter | Rows | Observable grain | Candidate source key |
| --- | --- | ---: | --- | --- |
| `Customer_Order.csv` | Semicolon | 122,370 | One order-detail source record, potentially repeated | None verified |
| `Picking_Wave.csv` | Semicolon | 215,192 | One picking-assignment source record; quantity is always 1 in this snapshot | None verified |
| `Product.csv` | Semicolon | 208 | One product reference | `Reference`, unique in this snapshot |
| `Storage_Location.csv` | Comma | 2,292 | One named location | `originalLocation`, unique in this snapshot |
| `Random_Storage.csv` | Comma | 2,292 | One scenario location with 18 encoded entries | `originalLocation`, unique within this file |
| `Class_Based_Storage.csv` | Semicolon | 2,341 | One scenario location with 18 encoded entries and a class label | `Location`, unique within this file |
| `Dedicated_Storage.csv` | Semicolon | 2,340 | One scenario location with 18 encoded entries and a class label | `Location`, unique within this file |
| `Hybrid_Storage.csv` | Semicolon | 2,340 | One scenario location with 18 encoded entries and a class label | `Location`, unique within this file |
| `Support_Points_Navigation.csv` | Semicolon | 44 | One labeled navigation coordinate | `labels`, unique in this snapshot |

Unique observed values are candidate keys, not a guarantee about future files. No CSV declares enforced primary or foreign keys.

## Customer_Order.csv

The source describes customer orders. Individual rows are not whole orders: there are 32,634 distinct order numbers. A source row is not a confirmed unique order line or completed pick.

| Exact source column | Documented meaning or observation | Proposed interpretation and restrictions |
| --- | --- | --- |
| `codCustomer` | Source describes a customer identifier; all records contain surrounding padding. | Text identifier; trim in a derived value. No separate customer master is supplied. |
| `orderNumber` | Source describes an order number. | Text identifier initially; repeated across detail records. Not a row key. |
| `orderToCollect` | Source describes a collection sequence number. | Integer-shaped sequence value; scope and ordering semantics unverified. Do not interpret as pick time or route sequence. |
| `Reference` | Product reference. | Text; candidate relationship to `Product.Reference`. |
| `Size (US)` | Source labels this US size; examples include `95`, `105`, and `255`; 16 blanks were found in the initial audit. | Preserve raw text. Cross-file size mapping and the apparent mixture of encodings remain unresolved. |
| `quantity (units)` | Source describes item quantity; initial audit found integer values from 0 to 120, including 33 zero-quantity records. | Integer units per source record, subject to quantity validation. Preserve zeros pending an explicit exclusion policy. Not completed output. |
| `creationDate` | Source describes order creation timestamp; observed format is day/month/year plus hour and minute. | Parse explicitly with `%d/%m/%Y %H:%M`. No timezone is supplied. Not pick start or finish time. |
| `waveNumber` | Picking wave identifier. | Text identifier initially; repeated across records. An order may span waves. |
| `operator` | Source describes the individual responsible for handling the order. | Text assignment label, not a verified employee identity or full workload measure. An order may span labels. |

Observed key checks:

- There are 2,559 excess exact duplicate records: total rows minus distinct full rows. This does not establish that they should be removed.
- Neither (`orderNumber`, `orderToCollect`) nor (`orderNumber`, `Reference`, `Size (US)`) is unique.
- Each order number has one customer label and one creation timestamp in the current snapshot. These are candidates for a later order-header table after loader validation.
- 4,024 orders span multiple waves and 3,584 span multiple operator labels. Wave and operator must remain at detail grain, or in an explicitly modeled relationship, rather than being forced into one value per order.

## Picking_Wave.csv

One row is one recorded assignment entry. Every `quantityToPick (units)` value is `1`, so row count equals assigned units in this snapshot only. Neither execution nor completion is established.

| Exact source column | Documented meaning or observation | Proposed interpretation and restrictions |
| --- | --- | --- |
| `waveNumber` | Picking wave identifier. | Text initially; not unique and not a record key. |
| `reference` | Product reference; note lowercase source spelling. | Text; candidate relationship to `Product.Reference`. Preserve source name when documenting lineage. |
| `Size (US)` | Source describes item size; values include `9.5`, `10.5`, and `255.0`. | Preserve raw text until the cross-file mapping is verified. Decimal casting alone does not resolve order values such as `95`. |
| `quantityToPick (units)` | Source describes quantity to pick; all current values are 1. | Validate integer units. Do not assume future files always use unit-level records. |
| `locations` | Source describes storage locations; all records contain padding. | Trim in a derived location code. Current values appear to be individual codes; no multi-location splitting rule is established. |
| `operator` | Source describes an assigned operator. | Text label; not a labor-hour denominator or confirmation of completion. |

There are 102,201 excess exact duplicate records. Repeated rows may represent multiple units with identical attributes; automatic deduplication would change quantities. Some waves contain multiple operator labels, so a wave header cannot require a single operator.

## Product.csv

| Exact source column | Meaning | Proposed interpretation and restrictions |
| --- | --- | --- |
| `Reference` | Product reference, unique across 208 rows. | Text primary-key candidate. Reference-level identity does not identify a specific size variant. |
| `ABCCOD` | Product classification label; observed values are A, B, C. | Text category. Calculation rules and reference period are unknown. |
| `Sector` | Source describes a warehouse sector. | Trimmed text is `PF` for all current products; not a useful comparison dimension in this snapshot. |

## Storage_Location.csv

| Exact source column | Meaning | Proposed interpretation and restrictions |
| --- | --- | --- |
| `originalLocation` | Named storage location, unique across 2,292 rows. | Text primary-key candidate. Do not infer zone or aisle semantics from code segments without validation. |
| `position` | Comma-separated coordinate representation. | Preserve text; compare parsed coordinates with `x`, `y`, `z` in a later validation task. Not a key: only 2,291 distinct strings were found. |
| `x` | X coordinate, documented as meters. | Numeric validation target; physical scale remains unverified. |
| `y` | Y coordinate, documented as meters. | Numeric validation target; coordinate distance does not prove walkable distance. |
| `z` | Z coordinate, documented as meters; supplied layout code treats Z values as floors. | Numeric validation target. Physical height versus floor-label meaning needs clarification before distance calculations. |

## Storage scenario files

Each file contains 18 encoded entries per location. The index identifies a source column, not a verified shelf position, capacity, quantity, or pick sequence.

| File | Exact location field | Exact classification field | Exact encoded-entry headers |
| --- | --- | --- | --- |
| `Random_Storage.csv` | `originalLocation` | None | `col_1` through `col_18` |
| `Class_Based_Storage.csv` | `Location` | `ABCCOD` | `1` through `18` |
| `Dedicated_Storage.csv` | `Location` | `XYZCOD` | `1` through `18` |
| `Hybrid_Storage.csv` | `Location` | `XYZCOD` | `1` through `18` |

Field contracts:

- Location fields are text and unique within each scenario. They are not globally unique if scenarios are combined.
- `ABCCOD` contains A/B/C labels. `XYZCOD` contains X/Y/Z/C labels; meanings and thresholds are not established, including the meaning of C.
- Every encoded entry currently splits into two components on a semicolon. Preserve the complete raw entry and both components as text if normalization is later approved.
- README describes `product_code;quantity`, but entries such as `8N10W9;11.0` resemble product-and-size combinations. The second component remains unresolved: neither inventory quantity nor size is an approved interpretation.
- The first component can be tested against product references, but that coverage does not by itself verify the entry's full meaning.
- A future normalized table could use (`scenario`, `location`, `slot_number`) as a technical key, with 18 slot records per source row. This is a proposal, not an implemented transformation. Never sum across scenarios as if they were simultaneous inventory snapshots.

## Support_Points_Navigation.csv

| Exact source column | Meaning | Proposed interpretation and restrictions |
| --- | --- | --- |
| `points_specified` | Text tuple such as `(66.0, -29.0, 1.0)`; coordinates documented as meters. | Preserve text. If parsed later, validate exactly three numeric components using safe parsing, never `eval()`. Coordinates are unique in this snapshot but do not establish navigation edges. |
| `labels` | Navigation point label, unique across 44 rows. | Text key candidate. Do not infer route connectivity or foreign keys from label appearance. |

The README calls this file `Support_Points.csv`; the actual source filename above is authoritative for file access.

## Candidate relationships and join contracts

| Relationship | Evidence in this snapshot | Contract for future analysis |
| --- | --- | --- |
| Order `Reference` to product `Reference` | All order references exist in the unique product reference set. | Many source records to one product. Validate uniqueness and coverage on every load before relying on a join. |
| Picking `reference` to product `Reference` | All picking references exist in the product set. | Many source records to one product; product is reference-level, not size-level. |
| Picking `locations` to location `originalLocation` | After trimming, 22 distinct picking codes are absent from the master. | Incomplete many-to-one candidate. Preserve unmatched records and report them; do not silently lose them through an inner join. |
| Order wave to picking wave | All picking wave IDs occur in orders; 77 order wave IDs have no picking records in the initial audit. | Raw records have a many-to-many relationship through wave. Aggregate each side independently to the same grain before joining. |
| Order header to detail records | Customer and creation timestamp are consistent within each order number in this snapshot. | Candidate one-to-many relationship. Enforce consistency checks before creating a header representation. |
| Storage scenario to location master | Random has no unmatched codes; class-based has 49; dedicated and hybrid each have 48. | Scenario location identity and snapshot compatibility require investigation; do not force all rows into the master. |
| Storage first component to product | Random, dedicated, and hybrid have full reference coverage; class-based has 109 distinct unmatched references. | Coverage is partial for class-based; retain evidence and defer enforced foreign keys for those entries. |

There is no verified direct order-line-to-picking-record foreign key. Wave + product may be useful for aggregate reconciliation, but is not a unique key on either raw table. Size-level comparisons additionally require a verified mapping. Operator labels need not agree between order and picking representations and must not be added to a join merely to make it look more specific.

## Deferred decisions

This task defines no final size mapping, duplicate-removal rule, zero-quantity exclusion, inventory metric, route model, or SQL schema. Those require separate evidence, review, and tested implementation. Definitions here must be updated if source documentation or a later validated rule changes our interpretation.
