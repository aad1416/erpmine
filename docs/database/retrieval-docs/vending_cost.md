# vending_cost

## Purpose
The historical purchase price ledger. It provides an immutable record of actual prices paid or quoted for a vendor-item relationship over time, serving as the basis for vendor performance analysis and inflation tracking.

---

## Retrieve This Table When The User Asks About

**Historical purchase prices and trends**
Vending finance tracking or price-over-time analysis for a specific SKU. Identifying what was actually paid on a particular purchase order.

**Vendor pricing analysis and inflation**
Tracking price escalations or renegotiation history with suppliers. Finding the last known purchase price for an item from a specific vendor.

---

## Co-Retrieved Sibling Tables
- `vending` — the current sourcing relationship.
- `purchase_orders` — the specific order that generated the cost record.
- `users` — the buyer who processed the transaction.
