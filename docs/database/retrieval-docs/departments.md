# departments

## Purpose
The functional organization of labor and processes. It represents internal teams and business units—such as "Assembly", "Sales", or "Electrical"—used to scope workflows and filter specialized manufacturing instructions.

---

## Retrieve This Table When The User Asks About

**Business units and internal teams**
Divisions or cost centers within a store. Identifying the functional groups that carry out day-to-day operations (e.g., "Sales team", geographic regions, regional teams like "Northeast").

**Workflow scoping and instructions**
Finding the department responsible for a specific set of manufacturing procedures (Instruction Sets). Ensuring a "Welding" or "Quality Assurance" tech only sees relevant procedures.

**System-standard and protected teams**
Identifying "Protected" system departments like "Production" or "Engineering" that drive core business logic.

---

## Co-Retrieved Sibling Tables
- `users_departments` — the staff members assigned to the team.
- `production_instruction_sets` — the technical manuals belonging to the department.
- `stores` — the branch that owns the functional unit.
- `users` — the manager who created the department definition.
