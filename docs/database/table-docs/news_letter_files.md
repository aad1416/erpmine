# `news_letter_files`

## Searchable Aliases
campaign attachments, newsletter media, marketing files

## Description
The `news_letter_files` table is the **Attachment Junction** for the **Lyndom** (the current PostgreSQL ERP) mass-communication domain. It serves as the logical link between a master `news_letters` campaign and the global `files` table (which stores the actual PDFs, images, or documents).

By using this junction, the system allows for the efficient reuse of technical documents or promotional flyers across different newsletter campaigns without duplicating the physical file data.

## ⚙️ The Attachment Lifecycle Workflow
1.  **File Staging**: An administrator uploads a document (e.g., "Safety Regulations v2.pdf") into the global `files` system.
2.  **Assignment**: The administrator links that file to a specific `newsletter_id` by creating a record in this table.
3.  **Refinement**: The `is_attached` boolean is used to determine if the file should actually be included as a physical attachment during the final email blast.
4.  **Delivery**: When the newsletter is triggered, the system iterates through these junction records to fetch the underlying file metadata for the mail-server.

## ⚠️ SQL-Critical Behaviors
- **Efficiency through Referencing**: Only the `file_id` (a UUID) and the link status are stored here. The actual file bytes and metadata remain in the central `files` table.
- **Toggle Control**: The `is_attached` flag provides a "Soft-Include/Exclude" mechanism, allowing managers to draft a campaign with several possible documents before finalizing the list for issuance.
- **Cascading Logic**: If a newsletter campaign is deleted, all records in this table are automatically purged, ensuring that the attachment links do not linger as orphans.

## Columns (7 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the attachment. |
| newsletter_id | uuid | no | — | Link to the parent campaign in `news_letters.id`. |
| file_id | uuid | no | — | **The Payload**: Link to the physical document in the `files.id` repository. |
| is_attached | bool | no | true | **Delivery Toggle**: If `false`, the link exists but the file won't be sent. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| newsletter_id | news_letters | id | cascade |
| file_id | files | id | cascade |

## Common Query Patterns
```sql
-- List all PDF attachments for a specific newsletter campaign
SELECT f.name, f.size 
FROM news_letter_files nlf
JOIN files f ON nlf.file_id = f.id
WHERE nlf.newsletter_id = '<newsletter_uuid>' 
  AND nlf.is_attached = true;

-- Audit: Verify which store branches are attaching a specific "Global Terms" document
SELECT DISTINCT store_id 
FROM news_letter_files 
WHERE file_id = '<file_uuid>';
```

## Indexes
- *Relies on standard relational indexes on `newsletter_id` and `file_id` for document bundling.*
