# `users_departments`

## Searchable Aliases
staff assignments, team membership, user business units

## Description
The `users_departments` table is a many-to-many junction that defines a user's organizational alignment within the business. By linking a `users.id` to a `departments.id`, the system identifies which functional group an employee belongs to (e.g., "Engineering", "Assembly", or "Sales"). **Live database analysis shows that users are frequently assigned to three or more departments simultaneously**, indicating that staff responsibilities in this ERP are broadly distributed across functional teams. This table is primarily used for task routing (notably in production and manufacturing) and for generating departmental resource reports.

## ⚠️ SQL-Critical Behaviors
- **Functional Assignment**: Used primarily to group users for specific production workflows or organizational reports.
- **Composite Primary Key**: No `id` column. Uses `(user_entity_id, department_entity_id)` for uniqueness.
- **No Metadata**: The table purely tracks the association without timestamps, relying on the parents (`users` or `departments`) for audit context.

## Columns

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| user_entity_id | uuid | no | Foreign key to `users.id`. |
| department_entity_id | uuid | no | Foreign key to `departments.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| user_entity_id | users | id | cascade |
| department_entity_id | departments | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all departments a specific user belongs to
SELECT d.name 
FROM departments d
JOIN users_departments ud ON d.id = ud.department_entity_id
WHERE ud.user_entity_id = '<user_uuid>';

-- Get a list of all users in the 'Electrical' department
SELECT u.full_name, u.email 
FROM users u
JOIN users_departments ud ON u.id = ud.user_entity_id
JOIN departments d ON d.id = ud.department_entity_id
WHERE d.name = 'Electrical';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| (user_entity_id, department_entity_id) | btree (PK) | Optimizes department-based lookups and ensures uniqueness. |


