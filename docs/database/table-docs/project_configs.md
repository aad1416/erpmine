# `project_configs`

## Searchable Aliases
global settings, system configuration, environment flags, deployment parameters

## Description
The `project_configs` table stores global, system-wide settings that apply to the entire ERP deployment. Unlike `store_configs`, which can vary by branch, the settings here define the core behavior of the platform's multi-tenancy and data-sharing logic. It currently manages the privacy visibility of item storefronts across the whole project.

> [!IMPORTANT]
> **No `store_id` Column — Global Singleton**: This table has **no `store_id` column** and cannot be filtered by branch. It is intended to have exactly **one row** for the entire deployment. Any attempt to add a `WHERE store_id = ...` clause here will result in a SQL error.

## ⚠️ SQL-Critical Behaviors
- **Singleton Pattern**: This table is intended to have **exactly one row**. Queries should never filter by ID but instead retrieve the single available record.
- **Global Flag**: The `is_item_store_private` column determines the default visibility of the product catalog. If `true`, item stores are likely hidden behind authentication by default across all branches. If `false` (as confirmed by live data), the item stores are likely publicly accessible in the storefront.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Update timestamp. |
| is_item_store_private | bool | no | — | Global switch for product catalog privacy. `false` = Public, `true` = Protected/Private. |

## Relationships

### References (FK Out)
- *None.*

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Retrieve the global privacy status for the entire project
SELECT is_item_store_private FROM project_configs LIMIT 1;
```

## Indexes
- *Uses default PK.*


