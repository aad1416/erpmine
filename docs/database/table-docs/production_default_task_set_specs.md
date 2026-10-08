# `production_default_task_set_specs`

## Searchable Aliases
default assembly specs, task template parameters, manufacturing presets

## Description
The `production_default_task_set_specs` table is the **Intelligent Dispatcher** for the manufacturing workflow. It defines the conditional logic that determines which standard tasks are assigned to a specific product build based on its technical specifications.

By mapping "Default Tasks" to "Spec Values," the **Lyndom** (the current PostgreSQL ERP) system automates the shop-floor guidance. This ensures that if a product variant requires specialized work (e.g., "High Pressure Testing"), the relevant task is automatically injected into the unit's build-list without manual oversight.

## ⚙️ The Task Dispatching Workflow
1.  **Rule Creation**: An engineer defines a rule linking a `production_default_task_id` to a target `category_id` and a specific technical requirement (e.g., "Material = Stainless Steel").
2.  **Product Audit**: When a unit build begins, the system scans the product master for all specifications matching the entries in this table.
3.  **Logical Firing**: For every match, the system "Fires" the rule, cloning the default task into the unit's active `production_tasks` ledger.
4.  **SOP Compliance**: This guarantees that the factory floor always follows the correct, up-to-date Standard Operating Procedure (SOP) for the exact model version being manufactured.

## ⚠️ SQL-Critical Behaviors
- **Conditional Multiplicity**: A single build can trigger dozens of tasks from this table. The final work order is the cumulative result of all matching specification rules.
- **Data Hardening**: The `spec_name` and `unit` are stored as text to preserve the logical definition of the rule even if the master specification definitions are modified in the catalog.
- **High-Performance Automation**: This table is queried at the moment of "Job Release," acting as the technical bridge between pre-sales engineering and shop-floor execution.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| production_default_task_id | uuid | no | — | Link to the template work order in `production_default_tasks.id`. |
| category_id | uuid | no | — | **The Domain**: The item category where this task is mandatory. |
| spec_id | uuid | no | — | Link to the technical characteristic in `specifications.id`. |
| spec_name | text | no | — | Denormalized name of the attribute (e.g., "Engine Displacement"). |
| value | text | no | — | **The Trigger**: The specific value that causes this task to be assigned. |
| unit | text | no | — | The unit of measure for the trigger value (e.g., "cc", "kg"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| production_default_task_id | production_default_tasks | id | cascade |
| category_id | categories | id | cascade |
| spec_id | specifications | id | cascade |

## Common Query Patterns
```sql
-- Find all task-assignment rules for the "Heavy Equipment" category
SELECT t.title, r.spec_name, r.value 
FROM production_default_task_set_specs r
JOIN production_default_tasks t ON r.production_default_task_id = t.id
WHERE r.category_id = '<cat_uuid>';

-- Audit: Identify which technical spec triggers the "Final Certification" task
SELECT spec_name, value, unit 
FROM production_default_task_set_specs 
WHERE production_default_task_id = '<task_uuid>';
```

## Indexes
- *Uses standard relational indexes on `production_default_task_id` and `category_id` for automated dispatching.*
