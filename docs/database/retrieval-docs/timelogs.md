# timelogs

## Purpose
The precision labor ledger. It captures the exact human effort (Clock-In/Clock-Out) expended on manufacturing and field service, providing the audit trail for payroll, performance KPIs, and final machine costing.

---

## Retrieve This Table When The User Asks About

**Labor tracking and clocked hours**
Technician time, billable hours, or timesheets. Identifying the exact human effort invested in a specific build or repair. Finding total technician labor for a field service unit.

**Efficiency and bottleneck analysis**
Tracking pause events and reasons to identify shop floor bottlenecks (waste time). Auditing the "Active" work history for a physical serial number.

**Actual vs Estimated labor costs**
Retrieving the "Observed" labor duration for a specific job. Providing the data that rolls up into the master unit labor cost.

---

## Co-Retrieved Sibling Tables
- `units` — the target machine being built or serviced.
- `users` — the worker whose time is being logged.
- `production_tasks` — the manufacturing task associated with the labor.
- `stores` — the branch where the labor occurred.
