# goods_issue_line_item_returns

## Purpose
The management system for returning unused or excess material to the warehouse. It allows for the correction of inventory balances when more parts were issued than actually consumed during assembly or field repair.

---

## Retrieve This Table When The User Asks About

**Returned materials and restock events**
Component returns from the assembly line or field back to the warehouse. Reversing an issuance event to put parts back into active stock.

**Net consumption and inventory accuracy**
Correcting stock levels to reflect net usage rather than gross issuance. Ensuring the warehouse shelf counts are updated when excess parts are physically put back in a bin.

**Material cost adjustments**
Reducing the accumulated part cost on a unit or service job when materials are returned. Identifying credits for unused components.

---

## Co-Retrieved Sibling Tables
- `goods_issue_line_items` — the original issuance line being reversed.
- `inventory_items` — the physical stock record being incremented.
- `goods_issues` — the parent issuance header.
- `users` — the staff member who registered the return and restocked the shelf.
