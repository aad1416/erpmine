# user_stores

## Purpose
The multi-tenant access control enforcer. It establishes the explicit link between users and stores, ensuring that staff (such as regional managers or floating technicians) can only access the specific branches they are authorized to see.

---

## Retrieve This Table When The User Asks About

**User access control and branch membership**
Staff permissions per store. Finding all stores that a specific user has authorized access to. Identifying all users who have access to a specific branch.

**Authorization auditing**
Checking when a user was granted access to a branch and by whom (creator). Auditing the multi-store access history for administrators or technicians.

---

## Co-Retrieved Sibling Tables
- `users` — the person receiving access.
- `stores` — the branch being accessed.
- `users` (as creator) — the manager who authorized the assignment.
