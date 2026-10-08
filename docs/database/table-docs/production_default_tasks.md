# `production_default_tasks`

## Searchable Aliases
standard assembly tasks, blueprint tasks, manufacturing templates

## Description
The `production_default_tasks` table is the **Job-Template Registry** for the manufacturing plant. It defines the standardized types of work orders (e.g., "Quality Control Audit", "Core Assembly") that occur repeatedly across different product builds.

This table acts as the master list of "Available Services" for the factory floor. When combined with specification-based rules, these default tasks are automatically cloned into a specific machine's `production_tasks` ledger, ensuring that every technician follows the same high-level workflow for consistency and quality management.

## ⚙️ The Workflow Standardization Process
1.  **Template Definition**: A production manager defines a standard task with a `title` and `description`.
2.  **Rule Mapping**: The task is linked to specific categories or SKU variants via the `production_default_task_set_specs` table.
3.  **Auto-Instantiation**: When a manufacturing job for a serialized unit is released, the system identifies all matching "Default Tasks" and creates active `production_tasks` records assigned to that unit.
4.  **Operational Continuity**: This ensures that even for complex, semi-custom builds, the core assembly and testing steps are never omitted.

## ⚠️ SQL-Critical Behaviors
- **Static vs. Dynamic**: Unlike the active `production_tasks` which track user-specific progress on a unique machine, `production_default_tasks` are **Global Templates**.
- **Template Retirement**: Setting `is_active = false` will prevent the task from being added to future builds, but the historical link for existing machines is preserved.
- **Blueprint Hierarchy**: This table is the foundational layer that drives the daily work-list generated for every technician on the shop floor.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this task template. |
| title | text | no | — | **Blueprint Name**: (e.g., "Final Painting & Finishing"). |
| description | text | no | — | Summarized instructions or scope defined for this template. |
| is_active | bool | no | true | Status flag. If `false`, the template is inactive for new job generation. |
| creator_id | uuid | no | — | The production manager who defined the template. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| production_default_task_set_specs | production_default_task_id | The technical rules that trigger this task for a SKU. |

## Common Query Patterns
```sql
-- List all standard tasks defined for a specific regional store
SELECT title, description 
FROM production_default_tasks 
WHERE store_id = '<uuid>' AND is_active = true;

-- Audit: Who is responsible for maintaining our shop-floor work templates?
SELECT t.title, u.email 
FROM production_default_tasks t
JOIN users u ON t.creator_id = u.id;
```

## Indexes
- *Relies on standard relational indexes on `store_id` for template management.*
