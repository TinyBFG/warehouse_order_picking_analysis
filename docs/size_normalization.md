# Size encoding investigation and proposed normalization

Investigated: October 31, 2026. Status: empirically verified against the current local snapshot; proposed for owner review. No production mapping or source transformation has been implemented. Approval of this document's recommendation and tested implementation are still required before a loader applies it.

## Problem and scope

Both `Customer_Order.csv` and `Picking_Wave.csv` label the field `Size (US)`, but their text representations differ. Orders include `95` and `105`, while picking includes `9.5` and `10.5`. Both also contain values in the 215 through 305 range. A blanket division by ten would corrupt values that already correspond numerically.

This investigation concerns cross-file comparison keys for these two CSVs only. It does not identify the physical size system, convert between US and other sizing standards, or establish the meaning of storage-scenario cell components. See [source dictionary](source_data_dictionary.md) and [provenance limitations](source_provenance.md).

## Observed domains

Orders contain 45 distinct nonblank size tokens plus 16 blank-size records. Picking contains 45 distinct nonblank size tokens and no blanks.

| Order token family | Picking numeric equivalent | Proposed canonical comparison value |
| --- | --- | --- |
| Integer strings `1` through `16` | `1.0` through `16.0` | Corresponding integer string, such as `10` |
| Ten explicit tokens in the mapping below | Half-size decimal strings | Corresponding decimal string, such as `9.5` |
| `215`, `220`, `225`, `230`, `235`, `240`, `245`, `250`, `255`, `260`, `265`, `270`, `275`, `280`, `285`, `290`, `295`, `300`, `305` | Corresponding value with `.0` | Unchanged integer string, such as `255` |
| Blank order size | No picking equivalent | Missing, not zero and not an inferred size |

All integers from 1 through 16 are present, including the low-frequency values 1, 2, and 3. The high-valued family is a separate observed token family; its physical unit or size standard is unknown.

## Explicit proposed order mapping

| Raw order token | Canonical comparison value | Single-size wave/product groups supporting this pairing |
| --- | --- | ---: |
| `35` | `3.5` | 2 |
| `45` | `4.5` | 6 |
| `55` | `5.5` | 50 |
| `65` | `6.5` | 264 |
| `75` | `7.5` | 965 |
| `85` | `8.5` | 2,246 |
| `95` | `9.5` | 3,271 |
| `105` | `10.5` | 3,371 |
| `115` | `11.5` | 156 |
| `125` | `12.5` | 46 |

These ten tokens affect 38,846 order records containing 67,383 recorded units. Mapping size labels changes neither record counts nor quantity totals.

For the remaining 35 nonblank order tokens, preserve their numeric values as canonical integer strings. Picking tokens are represented canonically by removing only redundant decimal zeros: `9.0` becomes `9`, `9.5` remains `9.5`, and `255.0` becomes `255`. Exact decimal parsing is suitable for a future implementation; binary floating-point conversion is unnecessary.

Treat this as a source-specific allowlist, not a general rule that removes or inserts decimal points. Unknown tokens in future files must be reported for review, not guessed. Preserve the raw token alongside the derived key, with a rule identifier such as `size_mapping_v1` if implemented. The canonical value is a matching label, not a validated physical measurement.

## Independent evidence and reconciliation method

1. Read both source CSVs as UTF-8 with optional BOM, using semicolons. Retain all repeated records, zero quantities, and blank sizes.
2. Group each file by wave and product, independently of operator. Select shared groups containing exactly one distinct raw size per side. This avoids choosing a pairing among multiple sizes within the group.
3. Observe the raw order/picking token pair in each selected group. There are 33,672 such groups. The 42 order tokens represented by this method each have only one observed picking partner, including all ten proposed changed tokens. This establishes consistent co-occurrence, not row-level linkage or guaranteed equal quantities.
4. Check the full domains. Removing the decimal point from the canonical picking labels produces exactly the 45 nonblank raw order tokens. This is a diagnostic observation, not a production parsing rule.
5. Verify sparse unchanged tokens 1, 2, and 3 separately within multi-size groups. They have 3, 2, and 2 common wave/product/size groups respectively, all with equal quantities. They have no single-size-group evidence; their support is narrower.
6. Aggregate order units and picking units separately at wave + product + canonical size. Do not join the raw rows. Do not include operator, since assignments across the two representations need not share the same label.
7. Compare group coverage and quantities before and after the proposed mapping. Baseline comparison already treats `9` and `9.0` as equivalent; it does not apply the ten half-size mappings.

No production analytical SQL was authored here. These read-only Python calculations support a data-quality decision; the later SQL analysis remains a separate learning task.

## Results

All counts below include source repeats and zero-quantity records. Missing sizes use a separate diagnostic group; they are not matched to actual size values.

| Metric at wave/product/size grain | Numeric baseline | Proposed mapping |
| --- | ---: | ---: |
| Order groups | 112,442 | 112,442 |
| Picking groups | 107,283 | 107,283 |
| Groups present on both sides | 72,056 | 107,283 |
| Common groups with equal quantities | 71,988 | 107,187 |
| Common groups with unequal quantities | 68 | 96 |
| Order-only groups | 40,386 | 5,159 |
| Picking-only groups | 35,227 | 0 |
| Units in order-only groups | 78,447 | 12,738 |
| Units in picking-only groups | 65,678 | 0 |
| Total order units | 228,195 | 228,195 |
| Total picking units | 215,192 | 215,192 |

The increase from 68 to 96 unequal common groups is not a deterioration caused by normalization: the mapped comparison brings previously unmatched groups into the comparison. Of the 107,283 mapped common groups, 107,187 agree exactly; the other 96 all have more order units than picking units, totaling a 265-unit difference.

The remaining total difference reconciles arithmetically:

`12,738 order-only units + 265 excess order units in common groups = 13,003 units`

`228,195 order units - 215,192 picking units = 13,003 units`

The 16 blank-size order records account for 20 units included in the order-only amount. They are retained, not assigned an inferred size. Order-only groups also reflect other coverage differences; they must not all be described as size errors or unfulfilled demand.

## Concrete source examples

Quantities below are independently aggregated from all matching source rows, without deduplication or operator filtering.

| Wave | Product | Raw order size | Raw picking size | Proposed key | Order units | Picking units |
| --- | --- | --- | --- | --- | ---: | ---: |
| `33168` | `8N10W9` | `95` | `9.5` | `9.5` | 2 | 2 |
| `33168` | `0LNUOV` | `105` | `10.5` | `10.5` | 1 | 1 |
| `33910` | `PY5UPB` | `255` | `255.0` | `255` | 5 | 5 |

## Collision and coverage checks

- All 45 nonblank observed order tokens are covered by the proposed allowlist.
- Their 45 canonical outputs are distinct: no two different order size tokens merge into one key.
- The canonical picking domain is also 45 distinct values and equals the mapped nonblank order domain.
- The order group count remains 112,442, so no previously separate order groups are collapsed by the proposal.
- All 107,283 picking groups have an order counterpart after mapping; this is stronger evidence than matching domains alone.
- The exact examples above and the 13,003-unit reconciliation were independently checked during the investigation.

## Proposed future loader contract

If approved, a later, separately tested implementation should:

1. Retain `size_raw` and derive a source-specific canonical key without modifying raw files.
2. Apply the explicit order-token allowlist and the approved picking-token representations only. Surface unknown tokens rather than silently accepting a new size domain.
3. Represent missing sizes as missing with a separate status; never zero-fill or match all missing records as if they were a real size variant. An outer comparison may retain them as unmatched evidence.
4. Validate mapping uniqueness, full observed-domain coverage, row counts, quantity totals, and reconciliation fixtures.
5. Preserve the distinction between empirical token equivalence and publisher-confirmed size semantics. Do not extend this mapping to storage scenarios automatically.

## Reproducing the principal comparison

The following read-only reference calculation can be run from the project root in Python. It prints metrics and writes no files. `Decimal` handles equivalent numeric spellings exactly. The `<missing>` marker is used only inside this diagnostic calculation, not as a proposed database value.

```python
import csv
from collections import Counter
from decimal import Decimal
from pathlib import Path

half_sizes = {
    '35': '3.5', '45': '4.5', '55': '5.5', '65': '6.5', '75': '7.5',
    '85': '8.5', '95': '9.5', '105': '10.5', '115': '11.5', '125': '12.5',
}

def aggregate(filename, product_field, quantity_field, mapping):
    groups = Counter()
    with (Path('data/raw') / filename).open(
        encoding='utf-8-sig', newline=''
    ) as handle:
        for row in csv.DictReader(handle, delimiter=';'):
            raw = row['Size (US)']
            size = Decimal(mapping.get(raw, raw)) if raw else '<missing>'
            groups[(row['waveNumber'], row[product_field], size)] += int(
                row[quantity_field]
            )
    return groups

picks = aggregate('Picking_Wave.csv', 'reference', 'quantityToPick (units)', {})
for label, mapping in [('baseline', {}), ('proposed', half_sizes)]:
    orders = aggregate('Customer_Order.csv', 'Reference', 'quantity (units)', mapping)
    common = orders.keys() & picks.keys()
    order_only = orders.keys() - picks.keys()
    pick_only = picks.keys() - orders.keys()
    print(label, {
        'order_groups': len(orders), 'pick_groups': len(picks),
        'common': len(common),
        'equal': sum(orders[k] == picks[k] for k in common),
        'unequal': sum(orders[k] != picks[k] for k in common),
        'order_only': len(order_only), 'pick_only': len(pick_only),
        'order_only_units': sum(orders[k] for k in order_only),
        'pick_only_units': sum(picks[k] for k in pick_only),
        'order_units': sum(orders.values()), 'pick_units': sum(picks.values()),
        'common_difference': sum(orders[k] - picks[k] for k in common),
    })
```

The reference code is intentionally limited to reproducing the comparison on this inspected snapshot. It is not a production allowlist validator and does not automatically approve future tokens.

## Decision and limitations

Recommend approving this source-specific mapping for future implementation because it is collision-free, has consistent independent single-size-group evidence for all changed tokens, and eliminates picking-only comparison groups without changing counts or units. The owner has not yet approved or deployed it.

No upstream transformation specification has been found. Empirical agreement cannot prove how sizes were originally encoded, the physical units, completion status, or the cause of quantity differences. New source versions require revalidation. The general source dictionary's deferred size decision remains in force until owner review and a later tested implementation.
