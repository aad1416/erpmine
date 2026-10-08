# fifo_reports

## Purpose
The authoritative financial ledger for inventory valuation. It implements First-In-First-Out (FIFO) accounting to track when dollar value is added to or removed from warehouse assets, serving as the primary source for COGS and audit reporting.

---

## Retrieve This Table When The User Asks About

**Inventory valuation and stock value**
Financial audit of warehouse assets. Tracking the total dollar value of stock on hand based on chronological entry. Analyzing the aging of cost layers for specific products.

**Cost accounting and COGS**
Calculating the Cost of Goods Sold (COGS) for a specific SKU or time period. Identifying the actual unit cost used for a particular sales order or consumption event (REDUCE records).

**Valuation adjustments**
Tracking dollar-value changes caused by receiving (ADD), consumption (REDUCE), or reconciliation (cycle count adjustments). Ensuring financial alignment with physical warehouse reality.

**Financial audit trails and paper references**
Cross-referencing dollar value changes with physical document numbers (e.g., PO numbers, receiving vouchers, issue numbers, count tags). Identifying the exact transaction that added or removed value from the asset.

---

## Co-Retrieved Sibling Tables
- `item_stores` — the branch SKU being valuated.
- `purchase_orders` — the buy order that established a cost layer (ADD).
- `receives` — the arrival event that added value.
- `goods_issues` — the consumption event that removed value (REDUCE).
- `cycle_counts` — the reconciliation that triggered a value adjustment.
