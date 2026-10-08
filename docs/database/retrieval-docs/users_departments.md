# users_departments

## Purpose
The staff assignment junction for business units. It defines a user's functional alignment within the organization, identifying which internal teams (e.g., Engineering, Assembly, Sales) an employee belongs to.

---

## Retrieve This Table When The User Asks About

**Team membership and staff assignments**
User business unit mapping. Finding all departments a specific user belongs to. Identifying multi-department responsibilities (where staff hold 3+ roles).

**Task routing and resource reporting**
Getting a list of all users in the "Electrical" or "Production" department for manufacturing task routing. Generating departmental resource and labor reports.

---

## Co-Retrieved Sibling Tables
- `users` — the staff member.
- `departments` — the functional team or division.
