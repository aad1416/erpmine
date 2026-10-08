# field_service_tasks

## Purpose
The execution layer for field repairs and maintenance. It defines specific, assignable actions (e.g., PCB replacement, sensor calibration) required to resolve a support ticket, tracking the timing, assignments, and completion of on-site work.

---

## Retrieve This Table When The User Asks About

**Repair jobs and maintenance tasks**
Technician assignments, on-site work orders, or specific repair actions. Identifying the scope of work (description) for a field technician.

**Technician scheduling and assignments**
Finding which technician is assigned to a specific repair. Tracking work deadlines (due dates) for SLA compliance. Identifying technicians performing inspections or administrative service tasks.

**Labor duration and time capture**
Calculating the "Labor Duration" of a specific repair action (start/end timestamps). Monitoring the status (Pending, In Progress, Completed) of field assignments.

**On-site context and logistics**
Retrieving unit serial numbers and sales order context for a technician's work-list. Searching for tasks using their human-readable ID.

---

## Co-Retrieved Sibling Tables
- `field_service_tickets` — the parent technical support case.
- `users` — the technician performing the work.
- `units` — the physical asset being serviced.
- `sales_orders` — the commercial parent of the machine.
- `contacts` — the client contact who requested the site visit.
