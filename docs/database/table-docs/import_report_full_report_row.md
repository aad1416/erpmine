# `import_report_full_report_row`

## Searchable Aliases
data import details, migration logs, spreadsheet rows, entry verification

## Description
The `import_report_full_report_row` table is the **Forensic Error Ledger** for the **Lyndom** (the current PostgreSQL ERP) system. It stores the granular, row-by-row failures that occur during a bulk data import.

When an import job (tracked in `import_reports`) encounters data it cannot process (e.g., a missing mandatory field, an invalid SKU, or a malformed date), it records the specific failure here. This prevents the entire job from crashing and allows a human administrator to "Download the Error Report" to see exactly which lines in their source spreadsheet need correction.

## ⚙️ The Data Error Recovery Workflow
1.  **Validation Failure**: During an active import, the system hits a row (e.g., Row #45) with an invalid Price value.
2.  **Evidence Capture**: Instead of stopping, the system creates a record in this table. 
3.  **Content Recording**: It saves the `error` message (e.g., "Non-numeric value"), the raw `value` that failed, and the physical `row_number` from the spreadsheet.
4.  **User Correction**: The user reviews this table (via a "Full Report") to identify the exact rows in their Excel file that require fixing before a re-upload.

## ⚠️ SQL-Critical Behaviors
- **Original Value Preservation**: The `value` column stores the "Problematic String" exactly as it was found in the source file. This is critical for users to find the offending data in their master document.
- **Contextual Helper**: The `helper_value` is used for supplemental data that helps the system/user identify the row (e.g., the primary key or name of the entity that failed).
- **Cleanup Strategy**: These logs are often voluminous. In high-performance systems, they are frequently cleared once a user has acknowledged and resolved the import job.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| row_number | int4 | no | — | **Source Location**: The physical line number in the original Excel/CSV file. |
| error | text | no | — | **Failure Reason**: Detailed error message (e.g., "Duplicate SKU found"). |
| value | text | no | — | **The Offending Data**: The raw string that caused the failure. |
| helper_value | text | no | — | Supplemental context to help identify the record (e.g., "Client Name: XYZ"). |
| import_report_id | uuid | no | — | Link to the parent job in `import_reports.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| import_report_id | import_reports | id | cascade |

## Common Query Patterns
```sql
-- List the specific errors found in a failed import job
SELECT row_number, error, value 
FROM import_report_full_report_row 
WHERE import_report_id = '<uuid>' 
ORDER BY row_number ASC;

-- Identify the most common data entry errors across all imports
SELECT error, COUNT(id) as occurrences 
FROM import_report_full_report_row 
GROUP BY error 
ORDER BY occurrences DESC;
```

## Indexes
- *Relies on standard relational indexes on `import_report_id` for report generation.*
