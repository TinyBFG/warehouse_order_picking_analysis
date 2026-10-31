# Source provenance and limitations

Reviewed: October 30, 2026. This record describes the supplied local download, not a verified external publication. It separates observed evidence, source documentation claims, and unresolved questions.

## Acquisition record

| Item | Current evidence or status |
| --- | --- |
| Local source directory | `data/raw/` relative to the project root |
| Acquisition context | The project owner supplied this directory as the downloaded dataset. |
| Original dataset title and publisher | Unknown; not established by the supplied documentation. |
| Original download URL or repository | Unknown; no verified source link has been recorded. |
| Download date, version, and original archive | Unknown; filesystem timestamps are not treated as acquisition evidence. |
| Dataset license and required attribution | Not established from the reviewed material. |
| Real, simulated, anonymized, or randomized records | Unverified. Generic operator labels and scenario filenames do not establish how the data was generated. |
| Raw-file integrity baseline | No checksum manifest has been created yet. No claim of comparison with an upstream release is made. |

## Local evidence reviewed

The download contains 21 files: nine CSVs, four PDFs, four SVGs, one DWG, one notebook, and two text files. Original source files have not been edited as part of these project tasks.

| Evidence | Verified observation | What it does not establish |
| --- | --- | --- |
| `data/raw/README.txt` | Provides field descriptions for nine tabular datasets. | Does not identify the original publisher, publication URL, license, or generation process. |
| `data/raw/Link Colab.txt` | Empty, zero-byte file. | Provides no notebook or dataset URL. |
| `data/raw/Order_Picking_dataset.ipynb` | Contains one code cell that plots warehouse layouts. Its source references `/content/Positions.xlsx` and `/content/SupportPointsWarehouse.xlsx`; these workbooks are absent from the supplied directory. The notebook was read as JSON, not executed. | Does not explain order generation, assignment generation, scenario construction, or completion status. It is not a verified reproduction workflow for the supplied CSVs. |
| `data/raw/Layout_Z1.0.svg` | Embedded date is `2024-12-21T15:33:59.638047`; creator metadata names Matplotlib v3.8.0. | Does not establish dataset collection date, authorship, license, or coordinate accuracy. |
| `data/raw/Layout_Z2.0.svg`, `Layout_Z3.0.svg`, `Layout_Z4.0.svg` | Embedded dates are December 11, 2024; creator metadata names Matplotlib v3.8.0. | Does not establish that these layouts were in use during the order observation period. |
| Source file inventory | No file named as a license, citation, or source record was found. | A filename search is not proof that no upstream license exists. |

The layout PDFs and DWG were identified during the initial inventory but have not received visual or geometric validation. No external publication has been identified or checked in this task.

## Documented claims versus analytical interpretation

| Topic | Supplied documentation or observed evidence | Project treatment pending clarification |
| --- | --- | --- |
| Picking completion | README describes items to be picked and an assigned operator; no verified completion field is available. | Describe recorded picking assignments, not completed picks. |
| Storage entry meaning | README calls entries `product_code;quantity`; observed second components resemble size values used elsewhere. | Treat the size interpretation as a hypothesis. Do not sum these components as inventory quantities. |
| Navigation filename | README describes `Support_Points.csv`; supplied file is `Support_Points_Navigation.csv`. | Record the mismatch; do not invent a missing file or silently rename the source. |
| Storage column names | README refers to `col_1` through `col_18`; class-based, dedicated, and hybrid CSVs use numeric headers `1` through `18`. | Parse actual headers and document any derived renaming. |
| Coordinate units | README describes coordinates in meters. | Attribute units to the documentation; scale, traversability, and travel distances remain unverified. |
| Product classifications | Product file contains `ABCCOD`; storage files also include `XYZCOD`, with observed values including `C`. | Do not invent classification thresholds, calculation periods, or meanings for undocumented values. |
| Operator labels | Records contain labels such as `Operator_1`. | Do not claim these represent identifiable employees, anonymized employees, or a complete employee roster. |

## Open questions and required evidence

| Priority | Question | Evidence needed | Effect while unresolved |
| --- | --- | --- | --- |
| 1 | Where was this exact download obtained? | Original landing-page URL, publisher, dataset title, version, and download date if known. | Source attribution and acquisition instructions remain incomplete. |
| 1 | What license and attribution requirements apply? | License or reuse terms from the verified source, including any separate terms for drawings or code. | Do not describe the download as openly licensed or redistribute it as project-owned material. Raw data remains excluded from Git. |
| 1 | Are transactions and assignments observed, simulated, randomized, anonymized, or transformed? | Publisher methodology or accompanying paper explaining each dataset. | Restrict findings to patterns in the supplied records; do not generalize to a real warehouse or claim operational effects. |
| 1 | Do picking rows represent requests, allocations, attempts, or confirmed completion? | Source definition of the recording event and coverage. | Do not calculate completion rates, service levels, or employee output. |
| 2 | How are size values encoded across files? | Field mapping or transformation specification, checked against records. | Defer size-level reconciliation; never apply a blanket decimal shift. |
| 2 | What does the second storage-cell component mean, and how were scenarios built? | Scenario-generation documentation and field definitions. | Defer inventory totals and storage-policy performance comparisons. |
| 2 | Why do repeated rows, quantity differences, and unmatched locations occur? | Extraction rules, snapshot dates, record identifiers, and scope definitions. | Preserve source rows, report discrepancies, and avoid calling differences backlog or errors without evidence. |
| 2 | Do the drawings and location master describe the same warehouse version and coordinate system? | Layout version, units, location mapping, and navigation rules. | Limit spatial work to documented coverage and descriptive location concentration. |
| 3 | What do ABC/XYZ classes mean and when were they calculated? | Classification rules and reference period. | Use supplied labels descriptively; do not claim an independently validated demand classification. |

## Interpretation boundaries

Even if later confirmed as real operational data, these files do not provide defensible labor hours, shifts, availability, or measured picking durations. Assignment totals cannot establish units per labor hour, worker efficiency, or fairness of staffing.

If records are randomized or simulated, observed associations may reflect the generation procedure rather than operational behavior. If anonymized, the effect depends on what changed: consistent label replacement can preserve some relationships, while shuffled identifiers or altered quantities can invalidate them. None of these treatments is currently confirmed.

Order creation timestamps describe incoming order records, not picking execution times. Quantity differences are reconciliation findings, not proof of unfulfilled demand. Storage scenario names are labels, not evidence of tested operational improvements. Simple group differences do not establish causes.

## How to update this record

When source information becomes available, record the exact URL, publisher, version, access date, applicable terms, and supporting passage or section. Distinguish publisher statements from independently verified behavior. Retain unresolved questions until evidence addresses them; do not fill gaps using plausible assumptions.

No raw data, drawings, or notebook outputs are added to version control by this task. This document supplies no license for upstream material and makes no claim that publication rights have been verified.
