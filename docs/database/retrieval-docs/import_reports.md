# import_reports

## Purpose
The bulk ingestion monitor. It manages the metadata, ETA, and high-level outcomes for mass-data migrations—such as bulk item uploads or inventory adjustments—allowing administrators to track long-running background jobs.

---

## Retrieve This Table When The User Asks About

**Data migration and bulk uploads**
Software data import logs (CSV/Excel) or system synchronization events. Monitoring the active progress (processed rows vs. total) and ETA of a running ingestion job.

**Ingestion outcomes and audit**
Identifying failed imports or jobs with row-level errors for a specific branch or user. Retrieving the net success/failure statistics (summary) for a completed migration.

**Target domain tracking**
Identifying which ERP table (entity) was updated during a specific mass-data modification (e.g., 'items' or 'contacts').

---

## Co-Retrieved Sibling Tables
- `import_report_full_report_row` — the granular forensic error logs for specific spreadsheet lines.
- `stores` — the branch where the data was imported.
