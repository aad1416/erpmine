# `user_types`

## Searchable Aliases
user classifications, account types, staff vs admin, role types

## Description
The `user_types` table provides a high-level categorization of users into broad functional domains: `MANAGEMENT` and `STORE_EMPLOYEE`. While roles (in the `roles` table) define granular permissions, user types likely serve as "UI Switches" or "Panel Access" flags that determine which primary interfaces a user can access. Live data analysis reveals that these categories are not mutually exclusive; a single user can be assigned both `MANAGEMENT` and `STORE_EMPLOYEE` types simultaneously, granting them visibility across both the corporate management dashboards and the branch-specific operational panels.

## ⚠️ SQL-Critical Behaviors
- **Multi-Category Assignment**: Users can have multiple records in this table. When checking for a user's type, always use `IN` or `EXISTS` rather than assuming a single value.
- **UI Logic Association**: These types typically correspond to the `role_type_enum`. A user with a `MANAGEMENT` role will almost certainly have a `MANAGEMENT` entry in this table to enable the corresponding management interface.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of creation. |
| updated_at | timestamptz | no | — | Timestamp of last update. |
| user_id | uuid | no | — | Foreign key to `users.id`. |
| type | text | no | — | ⚠️ **UI Identity Category**. Defines which top-level panel the user accesses. Examples of actual values include: `MANAGEMENT`, `STORE_EMPLOYEE`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| user_id | users | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all users categorized as Management
SELECT u.full_name, u.email 
FROM users u
JOIN user_types ut ON u.id = ut.user_id
WHERE ut.type = 'MANAGEMENT';

-- Check if a specific user has both Management and Store Employee access
SELECT user_id 
FROM user_types 
WHERE type IN ('MANAGEMENT', 'STORE_EMPLOYEE')
GROUP BY user_id 
HAVING COUNT(DISTINCT type) = 2;
```

## Indexes
- *Uses default PK and FK constraints for indexing logic.*


