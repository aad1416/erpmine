# `timelogs`

## Searchable Aliases
time cards, labor tracking, clocked hours, technician time, billable hours, timesheets

## Description
The `timelogs` table is the **Precision Labor Ledger** for the entire enterprise. It captures the exact human effort expended on every manufacturing job and field service repair. 

In the **Lyndom** (the current PostgreSQL ERP) ecosystem, labor is never "Estimated" on a final record—it is **Observed**. Technicians "Clock In" and "Clock Out" of specific units, and this table stores the resulting audit trail. This data is the primary source for payroll, technician performance KPIs, and most importantly, the actual labor cost applied to the `units` table.

## ⚙️ The Labor Tracking Workflow
1.  **Clock-In**: A user begins work on a physical machine. A `timelogs` record is created with `status = 'ACTIVE'` and a `start` timestamp.
2.  **Activity Anchor**: Every log MUST be linked to a `unit_id` (The specific serial number being worked on). If the work is for a new build, it is also linked to a `production_task_id`.
3.  **Pauses**: If the worker takes a break or waits for materials, the system records the event in the `pauses` JSONB array, ensuring non-productive time is not billed to the machine's cost.
4.  **Clock-Out**: Once the task is finished, the `end` timestamp is recorded, and the system calculates the `total_time` (Work duration minus total pauses).
5.  **Cost Rollup**: The resulting time is multiplied by the user's or unit's labor rate and added to the `units.labor_cost`.

## ⚠️ SQL-Critical Behaviors
- **Asset Level Billing**: The mandatory `unit_id` is a key architectural rule. In Lyndom, human labor is always considered an "Investment" or "Service" performed on a specific physical asset.
- **Granular Pauses**: The `pauses` field is a JSONB array of objects `[{ "start": timestamp, "end": timestamp, "reason": string }]`. This provides a high-fidelity audit trail for identifying bottlenecks in the shop floor workflow.
- **Pre-Calculated Total**: The `total_time` column (typically in seconds or minutes) is updated upon completion to allow for rapid reporting without requiring complex Epoch math in every query.

## Columns (15 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch where the labor occurred. |
| user_id | uuid | no | — | **The Worker**: Link to the employee in `users.id`. |
| unit_id | uuid | no | — | **The Target**: The specific machine serial number being serviced/built. |
| production_task_id | uuid | yes | — | Link to the manufacturing task in `production_tasks.id`. |
| start | int8 | no | — | The exact start timestamp (Epoch). |
| end | int8 | yes | — | The exact completion timestamp (Epoch). |
| pauses | jsonb | no | `[]` | **Audit Trail**: JSON array of all pause/resume cycles. |
| note | text | yes | — | Short user note regarding the work performed. |
| description | text | yes | — | Detailed activity description for service reports. |
| total_time | int4 | no | — | **Elapsed Duration**: Net work time after subtracting pauses. |
| status | enum | no | — | **Current State**: (e.g., `ACTIVE`, `PAUSED`, `COMPLETED`). |
| creator_id | uuid | no | — | The user who registered the log entry. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| user_id | users | id | cascade |
| unit_id | units | id | cascade |
| production_task_id | production_tasks | id | set null |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Calculate total technician labor for a specific field service unit
SELECT u.email, SUM(t.total_time) as total_seconds
FROM timelogs t
JOIN users u ON t.user_id = u.id
WHERE t.unit_id = '<uuid>'
GROUP BY u.email;

-- Identify "Waste Time": Find logs with more than 3 pause events
SELECT id, user_id, jsonb_array_length(pauses) as pause_count
FROM timelogs 
WHERE jsonb_array_length(pauses) > 3;
```

## Indexes
- *Includes indexes on `unit_id`, `production_task_id`, and `user_id` for high-performance labor reporting.*
