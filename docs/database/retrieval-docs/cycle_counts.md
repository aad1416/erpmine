# cycle_counts

## Purpose
The management hub for physical inventory audits and reconciliation. It facilitates the comparison of "System Quantity" against "Physical Reality" (actual counts), ensuring inventory accuracy without requiring a full warehouse shutdown.

---

## Retrieve This Table When The User Asks About

**Inventory audits and stock counting**
Warehouse audits, stock verification events, or reconciliation projects for specific SKUs. Scheduling and tracking the progress of continuous inventory audits.

**Variance analysis and resolution**
Comparing the system's expected quantity (snapshot) against the actual reported count from the warehouse shelf. Identifying stock discrepancies or shrinkage. Finalizing the resolved quantity to update the master inventory ledger.

**Staff assignments and paper trails**
Assigning physical count tasks to specific employees. Tracking unique audit tags (tag numbers) to link system results back to physical bins or pallets.

**Mobile and scanner counts**
Identifying audits initiated directly via mobile devices or warehouse scanners (direct count flag).

---

## Co-Retrieved Sibling Tables
- `item_stores` — the branch SKU being audited.
- `inventory_items` — the physical stock records being reconciled.
- `users` — the manager who initiated the audit or the employee performing the count.
- `stores` — the branch conducting the audit.
