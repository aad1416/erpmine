# `google_drive_files`

## Searchable Aliases
cloud documents, external attachments, drive links, remote files, shared docs

## Description
The `google_drive_files` table is the **External Cloud Sync Registry** of the Digital Storefront (DS) domain. It manages the technical connection between the **Lyndom** (the current PostgreSQL ERP) system and external documents hosted on Google Drive.

Unlike the internal `files` table which stores binary data, this table stores **References** to remote assets. This allows the ERP to integrate with live Google Sheets used by customers or engineers for project data, site surveys, or mass catalog updates.

## ⚙️ The Cloud Synchronization Workflow
1.  **File Linkage**: A user provides a link to a Google Drive file.
2.  **Registration**: The system records the Google-native `file_id` (a string) and the document's `name`.
3.  **Type Validation**: The system verifies the document type via the `type` enum (e.g., `SHEET`).
4.  **Data Extraction**: Once registered, other system modules (like `import_reports`) can use this record to "pull" live data from the Google Sheet into the ERP's internal tables.

## ⚠️ SQL-Critical Behaviors
- **Non-UUID Identifiers**: The `file_id` column is a `text` field because it must store Google's proprietary alphanumeric file strings, which do not follow typical database UUID formats.
- **Access Scope**: Every cloud reference is pinned to a `store_id`, ensuring that Branch A's private Google Sheet data is not accessible by Branch B.
- **Mime Integrity**: The `mime_type` is captured to ensure the system only attempts to process files it can technically parse (e.g., `application/vnd.google-apps.spreadsheet`).

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch owning the external file link. |
| name | text | no | — | **Display Name**: The human-readable name of the file (e.g., "Client X Site Survey"). |
| file_id | text | no | — | **Google File ID**: The proprietary alphanumeric string used by Google Drive API. |
| mime_type | text | no | — | The technical file format (e.g., `application/vnd.google-apps.spreadsheet`). |
| type | enum | no | — | **Integration Role**: (currently limited to `SHEET`). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |

## Common Query Patterns
```sql
-- List all Google Sheets currently linked to a specific store
SELECT name, file_id 
FROM google_drive_files 
WHERE store_id = '<uuid>' AND type = 'SHEET';

-- Identify recently updated cloud links for audit
SELECT name, updated_at 
FROM google_drive_files 
ORDER BY updated_at DESC;
```

## Indexes
- *Relies on standard relational indexes on `store_id` for cloud data management.*
