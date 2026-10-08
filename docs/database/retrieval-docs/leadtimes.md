# leadtimes

## Purpose
The operational duration registry. It stores standardized time windows (in days) for business processes like production cycles or vendor procurement, facilitating the programmatic calculation of expected delivery and completion dates.

---

## Retrieve This Table When The User Asks About

**Delivery estimates and arrival dates**
Procurement delays, shipping windows, or vendor wait times. Finding the standardized duration (e.g., "1 week", "30 days") used to calculate an expected arrival date.

**Production cycles and wait times**
Operational wait times for manufacturing jobs or component builds. Using named lead times to programmatically estimate when a task will be finished.

---

## Co-Retrieved Sibling Tables
- `items` — the product blueprints with standard lead times.
- `item_stores` — branch-specific replenishment lead times.
- `stores` — the branch defining the operational speeds.
