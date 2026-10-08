# `production_tasks`

## Searchable Aliases
work orders, manufacturing jobs, assembly tasks, shop floor projects, build orders

## Description
The `production_tasks` table is the **Shop Floor Execution** layer of the Manufacturing domain. While the `boms` table defines "What" is being built, this table defines "Who" is building it and "What" the current progress is for a specific machine on the assembly line.

Every Production Task is a distinct, assignable unit of work (e.g., "Frame Assembly", "Electrical Wiring") performed on a unique physical machine (`unit_id`). It serves as the primary interface for technicians to log their progress and for managers to oversee the manufacturing bottleneck in real-time.

## ⚙️ The Manufacturing Job Workflow
1.  **Task Generation**: When a unit build is "Issued" to the floor, the system auto-generates a set of tasks based on the `production_default_tasks` templates.
2.  **Assignment**: A floor manager assigns a task to a specific technician (`assigned_to_id`).
3.  **Instruction Execution**: The technician follows the sequential `production_steps` linked to this task.
4.  **Labor Tracking**: The technician clocks into the task, creating a `timelogs` record linked to this `production_task_id`.
5.  **Completion**: Once all steps are marked as `done`, the task status is updated to `COMPLETED`, allowing the manufacturing job to progress to the next stage.

## ⚠️ SQL-Critical Behaviors
- **The Execution Anchor**: This table is the "Hook" for labor costs. Any `timelogs` entry with a `production_task_id` is automatically rolled up into the machine's final manufacturing cost.
- **Relational Integrity**: Every task must be linked to both a parent **Sales Order** (Commercial context) and a **Unit** (Physical context). 
- **Identity of Progress**: The `status` enum (e.g., `PENDING`, `IN_PROGRESS`, `COMPLETED`) is the primary driver for production-floor dashboards.

## Columns (14 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch manufacturing the product. |
| assigned_to_id | uuid | yes | — | **Technician**: Link to the user currently performing the task. |
| assigned_to_name | text | yes | — | Denormalized name of the technician for display on shop-floor tablets. |
| unit_id | uuid | no | — | **The Target Asset**: Link to the specific physical serial number. |
| sales_order_id | uuid | no | — | Link to the commercial contract in `sales_orders.id`. |
| description | text | no | — | Detailed summary of the work expected for this task. |
| number | text | no | — | **Task ID**: Human-readable serial number (e.g., PT-10022). |
| title | text | no | — | Short name of the task (e.g., "Final Quality Test"). |
| status | enum | no | — | **Operational State**: (Actual values include `PENDING`). |
| creator_id | uuid | no | — | The manager who sanctioned the work order. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| assigned_to_id | users | id | set null |
| unit_id | units | id | cascade |
| sales_order_id | sales_orders | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| production_steps | production_task_id | The individual instruction steps (checklists) for this work order. |
| timelogs | production_task_id | The labor hours logged specifically against this manufacturing task. |

## Common Query Patterns
```sql
-- Identify active bottlenecks: List all technicians with more than 3 PENDING tasks
SELECT assigned_to_name, COUNT(id) 
FROM production_tasks 
WHERE status = 'PENDING' 
GROUP BY assigned_to_name 
HAVING COUNT(id) > 3;

-- Audit: List all manufacturing work performed for a specific Sales Order
SELECT number, title, status, assigned_to_name 
FROM production_tasks 
WHERE sales_order_id = '<uuid>';
```

## Indexes
- *Uses standard relational indexes on `unit_id` and `sales_order_id` for document generation.*
