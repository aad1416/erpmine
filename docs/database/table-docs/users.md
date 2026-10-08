# `users`

## Searchable Aliases
staff, employees, workers, technicians, representatives, creators, owners, administrators

## Description
The `users` table is the foundational identity and authentication layer of the ERP system. It serves as a central repository for every individual who interacts with the platform—ranging from Super Administrators and Store Owners to Sales Representatives and Technicians. Beyond managing login credentials (username and password) and basic profile data, this table is the **identity reference** for the system's audit trail. Nearly every transactional record links back to a `users.id` via a `creator_id` — the actual audit records are stored in those 100+ tables, not here. The hierarchical nature of the system is reflected in the `creator_id` column; while most users are created by an administrator, the root system administrator (e.g., `hunter`) has a `NULL` creator ID.

## ⚠️ SQL-Critical Behaviors
- **Self-Reference**: The `creator_id` column points back to `users.id`. This represents the administrative hierarchy (e.g., the Admin who created a specific Staff account).
- **Soft Deletes**: Always filter `WHERE is_active = true` to retrieve only current users unless auditing historical data.
- **Ubiquitous Audit FK**: Almost every table in this database (100+ tables) contains a `creator_id` pointing to this table.
- **SQL Rule**: When asked "who created [record]", join the target table to `users` on `target.creator_id = users.id`.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. Unique identifier for the user. |
| created_at | timestamptz | no | — | Timestamp when the user account was created. |
| updated_at | timestamptz | no | — | Timestamp when the user account was last updated. |
| first_name | text | no | — | User's first name. |
| last_name | text | no | — | User's last name. |
| full_name | text | no | — | User's full name (usually `first_name` + `last_name`). |
| username | text | no | — | Unique login identification. |
| email | text | yes | — | User's email address. |
| phone | text | yes | — | User's phone number. |
| password | text | no | — | Hashed authentication password. |
| is_active | bool | no | true | Status flag. `true` for active users, `false` for disabled. |
| creator_id | uuid | yes | — | ⚠️ **Self-reference**: The ID of the user who created this account. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| creator_id | users | id | set null |

### Referenced By (FK In)

#### 1. Primary Business Relationships (Functional)
*These tables link to users for core business logic, not just auditing:*

| Table | Column | Meaning |
|-------|--------|---------|
| stores | owner_id | The user who owns/manages a store. |
| users_roles | user_entity_id | Assigns roles (permissions) to the user. |
| users_departments | user_entity_id | Assigns the user to a business unit. |
| user_stores | user_id | Multi-tenancy access control. |
| sales_orders | sales_person_id | The representative who made the sale. |
| timelogs | user_id | The worker who logged hours on a task. |

#### 2. Audit Trail Pattern (Global)
*The `users` table is referenced by **80+ other tables** via the `creator_id` column. Examples include:*
- `items`, `categories`, `stores`, `quotes`, `purchase_orders`, `shipments`, `rma`, etc.

## Common Query Patterns
```sql
-- Search for a user by their full name (indexed)
SELECT id, username FROM users WHERE full_name ILIKE '%John Doe%';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting users by registration date. |
| email | btree | Optimization for email-based searches. |
| full_name | btree | Optimization for searching by customer/staff name. |
| is_active | btree | Filtering active vs. disabled accounts. |
| username | btree (unique) | Fast lookup for authentication. |


