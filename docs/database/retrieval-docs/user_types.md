# user_types

## Purpose
High-level user classification. It categorizes accounts into broad functional domains—such as MANAGEMENT or STORE_EMPLOYEE—serving as primary UI switches that determine which dashboards and operational panels a user can access.

---

## Retrieve This Table When The User Asks About

**User classifications and account types**
Staff vs. Admin levels or role types. Finding all users categorized as "Management" for interface access audits.

**Interface and panel access logic**
Identifying which primary dashboard (Corporate vs. Branch) a user is authorized to use. Checking if a staff member has simultaneous access to both operational and management panels.

---

## Co-Retrieved Sibling Tables
- `users` — the individual being classified.
- `roles` — the granular security permissions that often correspond to the user type.
