# `users_roles`

## Searchable Aliases
user permissions, security assignments, role links

## Description
The `users_roles` table is a many-to-many junction that assigns specific permissions to individual users. Records in this table connect a `users.id` with a `roles.id`, effectively delegating the security responsibilities defined in the role to that person. Because this is a junction table, it supports flexible security modeling: **live data confirms that users frequently hold multiple roles simultaneously**.

**Additive Security Model**: A user's total effective capabilities are the **union** of all accesses from every role assigned to them. For example, a user with both `Manager Full Access` (79 MGMT permissions) and a `Store Owner` role (491 STORE_PANEL permissions) has 570 total permissions spanning both global and local scopes.

## ⚠️ SQL-Critical Behaviors
- **Composite Primary Key**: This table has no independent `id` column. It uses the combination of `(user_entity_id, role_entity_id)` as the primary key.
- **Assignment Logic**: To determine if a user has access to a feature, you must join `users` -> `users_roles` -> `roles`.
- **Stateless Assignment**: This table tracks only the relationship. It does not contain timestamps for when the assignment was made.

## Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| user_entity_id | uuid | no | Foreign key to `users.id`. |
| role_entity_id | uuid | no | Foreign key to `roles.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| user_entity_id | users | id | cascade |
| role_entity_id | roles | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all users that possess a specific role name
SELECT u.full_name 
FROM users u
JOIN users_roles ur ON u.id = ur.user_entity_id
JOIN roles r ON r.id = ur.role_entity_id
WHERE r.name = 'Manager Full Access';

-- Check if a specific user has a specific role assigned
SELECT EXISTS (
  SELECT 1 FROM users_roles ur 
  JOIN roles r ON r.id = ur.role_entity_id 
  WHERE ur.user_entity_id = '<user_uuid>' AND r.name = 'Manager Full Access'
);

-- Find users holding more than one role
SELECT u.full_name, COUNT(ur.role_entity_id) AS role_count, array_agg(r.name) AS roles
FROM users u
JOIN users_roles ur ON u.id = ur.user_entity_id
JOIN roles r ON r.id = ur.role_entity_id
WHERE u.is_active = true
GROUP BY u.full_name HAVING COUNT(ur.role_entity_id) > 1;

-- Find users with both global and local roles (dual-scope administrators)
SELECT u.full_name
FROM users u
JOIN users_roles ur ON u.id = ur.user_entity_id
JOIN roles r ON r.id = ur.role_entity_id
WHERE u.is_active = true
GROUP BY u.full_name
HAVING COUNT(DISTINCT r.type::text) > 1;
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| (user_entity_id, role_entity_id) | btree (PK) | Ensures uniqueness and optimizes join performance. |


