# roles

## Purpose
The Role-Based Access Control (RBAC) hub. It defines reusable sets of permissions and access levels—such as "Warehouse Manager" or "Field Technician"—that can be assigned to users to govern their privileges and authorization across the system.

---

## Retrieve This Table When The User Asks About

**Security profiles and access levels**
User groups, authorization, or privileges. Identifying which roles have a specific permission key (e.g., "ITEM_STORE_EDIT").

**System-critical and protected roles**
Identifying "Protected" system-default roles that are restricted from modification. Distinguishing between global roles and local, branch-specific roles.

**Organizational levels and management**
Finding roles within a specific scope (Management vs. Store). Identifying the engineer or admin who defined a security profile.

---

## Co-Retrieved Sibling Tables
- `users_roles` — the junction mapping roles to specific staff.
- `users` — the administrator who created the role.
- `stores` — the branch that owns a custom local role.
