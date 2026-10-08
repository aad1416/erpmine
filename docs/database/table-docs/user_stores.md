# `user_stores`

## Searchable Aliases
user access control, branch membership, staff permissions per store

## Description
The `user_stores` table is a critical junction that establishes the relationship between `users` and `stores`. In this multi-tenant system, being a User in the database does not automatically grant access to any store's data. Instead, access is explicitly granted through this table. This allows a single user (such as a regional manager or a technician) to have access to multiple different branches while preventing them from seeing data in branches they are not assigned to.

## ⚠️ SQL-Critical Behaviors
- **Access Control Enforcer**: When determining which stores a user is authorized to query, you must join `users` -> `user_stores` -> `stores`.
- **Primary vs. Multiple**: A user can have many records here (multi-store access), which is common for administrators and floating technicians.
- **Audit Requirement**: Every record tracks its own `created_at` and `creator_id`, allowing you to audit when a user was granted access to a specific branch and by whom.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp when access was granted. |
| updated_at | timestamptz | no | — | Last modification of the link. |
| store_id | uuid | no | — | The store the user is given access to. |
| user_id | uuid | no | — | The user receiving access. |
| creator_id | uuid | no | — | The user who authorized this store assignment. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| user_id | users | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all stores that a specific user has access to
SELECT s.name 
FROM stores s
JOIN user_stores us ON s.id = us.store_id
WHERE us.user_id = '<user_uuid>';

-- Find all users who have access to a specific store
SELECT u.full_name, u.email
FROM users u
JOIN user_stores us ON u.id = us.user_id
WHERE us.store_id = '<store_uuid>';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Auditing assignment history. |
| store_id | btree | Optimization for finding all staff at a store. |
| user_id | btree | Optimization for finding all stores for a user. |


