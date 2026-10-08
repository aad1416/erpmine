# `production_steps`

## Searchable Aliases
technical actions, assembly steps, workstation tasks, manual entries, technician instructions

## Description
The `production_steps` table is the **Surgical Instruction Layer** of the assembly line. While a `production_task` defines a broad work order, the `production_steps` table defines the specific, sequential actions—technical instructions, measurements, and safety checks—that a technician must execute to satisfy the task.

It acts as a digital technical manual, guiding the worker through complex assembly processes and enforcing a "Stop-and-Check" workflow where every step must be electronically signed off.

## ⚙️ The Instructional Workflow
1.  **Instruction Injection**: When a `production_task` is created, the system populates this table with steps derived from the `instructions` template.
2.  **Technician Guidance**: The worker views the `title`, `subtitle`, and `content` on a shop-floor tablet.
3.  **Data Capture**: If the step requires a measurement (e.g., "Record Resistance Value"), the worker inputs data into the `args` or `checkboxes` JSONB fields.
4.  **Sign-Off**: Once a step is finished, the `done` flag is toggled to `true`.
5.  **Sequential Locking**: In many shop-floor configurations, Step 2 cannot be performed until the `done` flag for Step 1 is verified.

## ⚠️ SQL-Critical Behaviors
- **Granular Traceability**: By linking to both `production_task_id` and `unit_id`, the system maintains a permanent record of exactly *How* a specific serial number was built, including any technical measurements captured during assembly.
- **Flexible Data Schema**: Use of `args` and `checkboxes` (JSONB) allows for diverse instruction types—from simple "Read-Only" warnings to complex data-entry forms—without schema changes.
- **WBS Pathing**: The `step` column (often numeric or dot-notation) determines the chronological sequence in which tasks are presented to the worker.

## Columns (15 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch manufacturing the product. |
| production_task_id | uuid | no | — | Link to the parent work order in `production_tasks.id`. |
| unit_id | uuid | no | — | **The Target Asset**: Link to the physical machine being built. |
| done | bool | no | false | **Execution Status**: If `true`, the technician has completed the step. |
| title | text | no | — | **Action Name**: (e.g., "Main Board Inspection"). |
| subtitle | text | no | — | Brief instruction or category for the step. |
| content | text | no | — | **The Manual**: Full technical instructions/methodology for the step. |
| step | text | no | — | **Sequence ID**: Numeric or alphanumeric order (e.g., `1`, `2.1`). |
| args | jsonb | no | — | **Parameter Capture**: User-provided measurements (e.g., `{ "voltage": 12.4 }`). |
| checkboxes | jsonb | no | — | **Validation Capture**: List of internal verification flags checked by the user. |
| creator_id | uuid | no | — | The manager or system that generated the step record. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| production_task_id | production_tasks | id | cascade |
| unit_id | units | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Track Progress: Find all incomplete steps for a specific unit build
SELECT title, step, content 
FROM production_steps 
WHERE unit_id = '<uuid>' AND done = false 
ORDER BY step ASC;

-- Audit: Extract technical measurements (args) for a specific assembly step
SELECT unit_id, args 
FROM production_steps 
WHERE title = 'Final Calibration' AND done = true;
```

## Indexes
- *Uses standard relational indexes on `production_task_id` and `unit_id` for document generation.*
