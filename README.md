# Warehouse Order Demand & Picking Assignment Analysis

A SQL-focused data analyst portfolio project investigating recorded warehouse demand, picking assignments, and workload distribution. The project combines reproducible engineering with analyst-authored SQL and documented business interpretation.

## Business question

Where are recorded picking assignments concentrated, how do wave workloads differ, and which demand or data-quality patterns should warehouse management investigate?

Assignment counts describe recorded allocation. They do not establish employee efficiency, staffing fairness, or completed work.

## Scope

The core analysis will examine:

- Reconciliation of order quantities and picking quantities at compatible grains.
- Wave workload size and complexity using units, distinct products, and distinct locations.
- Product demand concentration and recorded assignment distribution across operator labels.
- Picking location concentration and location-master coverage.
- Orders split across waves and order creation-date demand patterns.

Storage-scenario comparisons are a possible extension, pending clarification of encoded fields, unmatched references, and scenario provenance. Labor productivity, actual travel distance, route optimization, and causal claims are outside the current scope.

## Current status

The initial read-only feasibility audit is complete. Repository foundation work is underway. No project ingestion pipeline, SQLite database, analytical SQL, KPI workbook, or dashboard has been implemented yet.

The counts below were checked directly against the local source files. They are raw-source observations, not validated business KPIs. Repeated records are retained.

| Source observation | Value |
| --- | ---: |
| Customer order records | 122,370 |
| Distinct order numbers | 32,634 |
| Sum of recorded order quantities | 228,195 units |
| Picking records | 215,192 |
| Sum of recorded picking quantities | 215,192 units |

Order creation timestamps, parsed as day/month/year, range from January 5 through October 19, 2023. They do not measure when picking occurred. The difference between order and picking totals must not be interpreted as unfulfilled demand without further investigation.

## Source data

Original downloads are kept unchanged in `data/raw/` and excluded from version control.

| Source group | Files | Apparent purpose |
| --- | --- | --- |
| Order demand | `Customer_Order.csv` | Order-detail records with product, size, quantity, creation timestamp, wave, and operator label |
| Picking assignments | `Picking_Wave.csv` | Recorded unit-level assignments with product, size, wave, location, and operator label |
| Reference data | `Product.csv`, `Storage_Location.csv` | Product classifications and location coordinates |
| Storage scenarios | `Random_Storage.csv`, `Class_Based_Storage.csv`, `Dedicated_Storage.csv`, `Hybrid_Storage.csv` | Alternative location layouts containing encoded storage entries |
| Navigation and drawings | `Support_Points_Navigation.csv`, four layout PDFs, four layout SVGs, `Full layout.dwg` | Navigation coordinates and warehouse layout references |
| Supporting material | `README.txt`, `Order_Picking_dataset.ipynb`, empty `Link Colab.txt` | Field descriptions and layout plotting code |

The CSV files use both comma and semicolon delimiters. Source provenance, licensing, anonymization, and possible simulation or randomization have not yet been established from the supplied documentation. This repository does not redistribute the raw download or claim a license for it.

## Analytical limitations and validation priorities

- No defensible labor-hour, shift, completion-time, or downtime measurements are available. Units per labor hour and employee performance rankings cannot be calculated.
- Exact repeated rows occur in both order and picking files. They must not be removed until their meaning is established; repeated unit assignments may be legitimate.
- Size encodings differ between orders and picking records. A verified mapping is needed before size-level reconciliation.
- Some order sizes are missing and some order quantities are zero. Exclusion rules remain to be defined.
- Identifiers contain padding, and some picking locations are absent from the location master. Derived normalization must preserve traceability to source values.
- Orders can span waves and operators, and waves can contain multiple operators. Raw tables must not be joined on wave alone; aggregate to a compatible grain first to avoid multiplying quantities.
- The meaning of storage-cell values is unresolved. The supplied description calls the second component quantity, while observed values resemble sizes. Inventory totals and scenario comparisons are deferred.
- Coordinates alone do not establish traversable routes, actual distance, or travel time.

Any eventual recommendations will distinguish observations from hypotheses and identify additional evidence management would need.

## Planned tools and deliverables

| Tool | Planned role |
| --- | --- |
| SQL and SQLite | Relational modeling, analytical queries, and reconciliation checks |
| Python | Source inspection, reproducible ingestion, and data-quality checks |
| pytest | Focused tests for ingestion and validation logic |
| Google Sheets | Auditable KPI workbook and operational scorecard |
| Tableau Public | Interactive dashboard based on validated exports |
| Git and GitHub | Version control, documentation, and portfolio publication |

These are planned deliverables, not claims of completed artifacts. Important analytical SQL will be written or meaningfully revised by the project author.

## Reproduction and development

There is no build or analysis command yet. Dependency setup, source acquisition instructions, schema definitions, and execution commands will be documented when implemented and verified. The supplied notebook has not been executed as part of this project.

Work proceeds in small, reviewed tasks. Each implementation receives an explanation, relevant verification, and a proposed Git checkpoint. Original data remains immutable, and source rows are preserved until explicit, tested transformation rules are approved.
