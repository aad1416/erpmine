# `import_reports`

## Searchable Aliases
data migration, bulk uploads, import logs, system synchronization, file imports

## Description
The `import_reports` table is the **Bulk Ingestion Monitor** of the **Lyndom** (the current PostgreSQL ERP) system. It manages the metadata, progress, and high-level outcomes for automated software data migrations—such as bulk CSV item uploads, Excel inventory adjustments, or contact imports.

**Note:** This table tracks software data ingestion only. It does NOT track physical overseas shipping, containers, or customs.

## ⚙️ The Data Ingestion Workflow
1.  **Job Initiation**: A user selects a file (Excel/CSV) and a target `entity` (e.g., `'items'`).
2.  **Record Creation**: An `import_reports` record is created, capturing the `total_rows` and the starting `status`.
3.  **Active Processing**: As the worker process consumes the file, it updates `processed_rows` and calculates the `estimated_seconds_remaining`.
4.  **Error Logging**: Any specific row-level failures are recorded in the `import_report_full_report_row` table.
5.  **Completion**: The final `status` (e.g., `COMPLETED`) is set, and a high-level statistics blob is stored in the `summary` JSONB.

## ⚠️ SQL-Critical Behaviors
- **Real-Time Instrumentation**: The `processed_rows` and `estimated_seconds_remaining` columns are designed for high-frequency updates to drive progress-bar UIs in the dashboard.
- **Outcome Auditing**: The `summary` JSONB column caches the net result (e.g., "Successes: 98, Errors: 2"), providing an instant audit without needing to scan thousands of row-level error logs.
- **Traceability**: The `user` field (text) and `store_id` (UUID) identify exactly who triggered the mass-data modification and within which branch it occurred.

## Columns (12 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch where the data is being imported. |
| user | text | no | — | **Operated By**: The name or identifier of the user who triggered the job. |
| status | enum | no | — | **Current Job State**: (e.g., `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`). |
| date | int8 | no | — | The authoritative timestamp of the import event (Epoch). |
| estimated_seconds_remaining | int4 | no | 0 | **ETA**: Time until the process completes. |
| entity | text | no | — | **Target Domain**: The table being updated (e.g., `'product_category'`). |
| summary | jsonb | no | — | **Net Statistics**: Aggregated counts of success/failure/skips. |
| total_errors | int4 | no | — | The count of rows that failed to import correctly. |
| processed_rows | int4 | no | — | The count of rows that have been handled so far. |
| total_rows | int4 | no | — | The final count of all data rows in the source file. |

## Enums Used
### `import_report_status`
- `PENDING`: Waiting for a background worker.
- `PROCESSING`: Currently reading and inserting data.
- `COMPLETED`: Finished with or without errors.
- `FAILED`: System-level crash or fatal interruption.

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| import_report_full_report_row | import_report_id | The granular, per-row error logs for this import. |

## Common Query Patterns
```sql
-- Find failed imports for the current store in the last 24 hours
SELECT entity, total_errors, user 
FROM import_reports 
WHERE store_id = '<uuid>' 
  AND status = 'FAILED'
  AND created_at > (NOW() - INTERVAL '1 day');

-- Monitor active progress for all currently running jobs
SELECT user, entity, processed_rows, total_rows, estimated_seconds_remaining
FROM import_reports 
WHERE status = 'PROCESSING';
```

## Indexes
- *Uses standard relational indexes on `store_id` and `status` for management monitoring.*
