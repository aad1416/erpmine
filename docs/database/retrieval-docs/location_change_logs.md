# location_change_logs

## Purpose
The immutable chain of custody for physical inventory. It records every instance of stock moving from one warehouse bin to another, providing a detailed audit trail for relocation forensics and warehouse velocity tracking.

---

## Retrieve This Table When The User Asks About

**Stock movement and transfer history**
Bin transfer logs, warehouse relocation audits, or stock movement history for a particular SKU. Tracking the travel path of an item across the warehouse.

**Relocation responsibility and auditing**
Identifying the staff member (mover) who relocated stock from a source bin (before location) to a destination bin (after location). Providing a chronological record of warehouse activity.

**Warehouse velocity and slotting**
Analyzing how frequently an item is moved to optimize bin placement (warehouse slotting). Identifying high-velocity SKUs that move between zones often.

---

## Co-Retrieved Sibling Tables
- `inventory_items` — the stock that was moved.
- `locations` — the source and destination bins.
- `users` — the staff member who performed the move.
- `item_stores` — the branch SKU being relocated.
