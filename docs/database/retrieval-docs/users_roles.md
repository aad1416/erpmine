# users_roles

## Purpose
The security assignment junction. It maps specific permissions (roles) to individual users, supporting an additive security model where a person's total privileges are the union of all roles assigned to them.

---

## Retrieve This Table When The User Asks About

**User permission and security assignments**
Role links or staff privilege mapping. Finding all users that possess a specific role (e.g., "Service Tech", "Technician").

**Access verification**
Checking if a specific user has "Admin" or "Store Manager" privileges. Determining if a staff member is authorized for a specific system feature.

**Department manager and job-title based staff lookup**
Finding all managers or staff with a specific position (e.g., "Accounting Manager", "Production Lead"). Listing which users in a specific department hold a management or supervisory role.

---

## Co-Retrieved Sibling Tables
- `users` — the staff member receiving the permissions.
- `roles` — the security profile being assigned.
