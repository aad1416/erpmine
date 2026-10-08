# production_tasks

## Purpose
The shop floor execution layer. It manages the active work orders and assembly jobs for specific machines, defining who is building what and tracking the current operational progress on the assembly line.

---

## Retrieve This Table When The User Asks About

**Manufacturing jobs and work orders**
Shop floor projects, assembly tasks, or build orders (e.g., "Frame Assembly", "Wiring"). Identifying the current workload for a physical machine.

**Technician assignment and bottlenecks**
Finding which technician is assigned to a specific task. Identifying manufacturing bottlenecks by listing technicians with heavy work-lists.

**Operational progress and dashboards**
Tracking task statuses (Pending, In Progress, Completed) for production-floor dashboards. Auditing all work performed for a specific Sales Order or Unit.

**Overdue, late, and past-due work orders**
Identifying manufacturing tasks that have passed their scheduled end date. Finding assembly jobs that are behind schedule or have not been completed on time.

**Labor cost aggregation**
Identifying the "Execution Anchor" for labor. Any work logged against a task here is automatically rolled up into the final unit manufacturing cost.

---

## Co-Retrieved Sibling Tables
- `units` — the specific serial number being built.
- `production_steps` — the individual instructions/checks for the task.
- `timelogs` — the actual labor hours clocked against the job.
- `users` — the technician or manager involved.
- `sales_orders` — the commercial parent of the build.
