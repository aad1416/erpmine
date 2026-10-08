# part_request_line_items

## Purpose
The digital "Pick List" for internal requisitions. it specifies the exact SKU-level components and quantities required from stock for a build or repair, tracking the gap between what was requested and what has been physically issued.

---

## Retrieve This Table When The User Asks About

**Requested parts and component needs**
Sub-assembly requests or material requisition lines. Identifying the exact SKU (item number) needed for a shop floor task.

**Internal shortages and fulfillment tracking**
Finding critical internal shortages where the requested quantity exceeds the issued (physically picked) quantity. Auditing the "Issued Quantity" subtracted from stock.

**Historical request snapshots**
Retrieving the "As-Requested" technical details (name/number/description) of a part for a specific repair or build, ensuring data continuity even if catalog names change.

---

## Co-Retrieved Sibling Tables
- `part_requests` — the parent requisition header.
- `item_stores` — the branch SKU being requested.
- `goods_issue_line_items` — the final consumption record.
