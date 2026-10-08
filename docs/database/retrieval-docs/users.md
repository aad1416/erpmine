# users

## Purpose
The foundational identity and authentication layer. It serves as the master registry for staff, employees, and technicians, providing the anchor for the system's global audit trail through creators and ownership links.

---

## Retrieve This Table When The User Asks About

**Staff and employee identity**
Searching for users by name, email, or username. Finding the contact details (phone/email) for a specific employee or representative.

**Administrative hierarchy and accountability**
Identifying "Who" created a specific user account or staff record. Finding the account owner for a particular store.

**Audit trails and record creation**
Finding the user responsible for creating any transactional record (e.g., "Who created this quote?"). Joining to almost any table in the database to identify the human actor (creator).

**Account status and activity**
Filtering for active vs. disabled (is_active) employees. Identifying administrative staff vs. technicians.

---

## Co-Retrieved Sibling Tables
- `roles` — the security profiles and permissions assigned to the user.
- `departments` — the business unit or team membership (e.g., Sales, Engineering).
- `stores` — the branch(es) the user is authorized to access.
- `timelogs` — the recorded labor hours for the worker.
- `sales_orders` — the commercial sales made by the representative.
