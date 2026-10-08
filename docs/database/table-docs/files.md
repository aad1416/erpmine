# `files`

## Searchable Aliases
documents, attachments, uploads, images, pdfs, digital assets, cloud storage

## Description
The `files` table is the **Central Media Repository** for the **Lyndom** (the current PostgreSQL ERP) system. It acts as a universal attachment engine, storing the metadata, references, and ownership details for every binary asset in the application—from product photos and technical CAD drawings to vendor quote PDFs and customer signatures.

By using a polymorphic architecture, this single table anchors all "Attached Documents" across every ERP module, providing a consistent way to manage file access, search, and storage.

## ⚙️ The Polymorphic Attachment Workflow
1.  **Upload**: A user uploads a file through any module (e.g., adding an image to a Product or a PDF to a Purchase Order).
2.  **Polymorphic Anchoring**: The system creates a record in this table, recording the `owner_id` (the target record's UUID) and the `owner_type` (e.g., `'item'`, `'purchase_order'`, `'checklist_item'`).
3.  **Classification**: The `file_type` (MIME type) and `name` are recorded to ensure the front-end knows how to handle the asset (e.g., render as an image vs. download as a file).
4.  **Retrieval**: When a user views the Purchase Order, the system queries this table for all files where `owner_id` matches, presenting the "Attachments" list to the user.

## ⚠️ SQL-Critical Behaviors
- **Entity Agnostic Storage**: This table does not have hard Foreign Keys to domain tables like `items`. Instead, it uses a string-based `owner_type` to maintain flexibility.
- **Multi-Tenant Security**: While many files are global (e.g., product images), the `store_id` allows for branch-specific sensitive documents (e.g., local hire contracts or site survey results).
- **Soft Deletion**: The `is_active` flag allows for the quick removal of files from the UI while preserving the record for system audits.

## Columns (12 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | yes | — | **Tenant ID**: The branch that owns or uploaded the asset. |
| owner_type | text | no | — | **Link Target Type**: (e.g., `'item'`, `'production_task'`, `'client'`). |
| owner_id | text | no | — | **Link Target ID**: The identifier of the record this file is attached to. |
| name | text | no | — | **Filename**: The actual name of the file (e.g., "manual_v2.pdf"). |
| title | text | yes | — | **Public Label**: A human-friendly title for the attachment. |
| description | text | yes | — | Detailed notes regarding the file's content or version. |
| file_type | text | no | — | **MIME Type**: (e.g., `image/jpeg`, `application/pdf`). |
| is_active | bool | no | true | Status toggle. If `false`, the file is hidden from the UI. |
| creator_id | uuid | no | — | **The Author**: Link to the user who uploaded the file. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| *Polymorphic* | *owner_id* | This table is the "Attachment Hub" for the entire system. |

## Common Query Patterns
```sql
-- List all PDF documents attached to a specific Sales Order
SELECT name, title, created_at 
FROM files 
WHERE owner_id = '<uuid>' 
  AND owner_type = 'sales_order' 
  AND file_type = 'application/pdf';

-- Audit: Identify high-volume file uploads by a specific user
SELECT COUNT(id), owner_type 
FROM files 
WHERE creator_id = '<user_uuid>' 
GROUP BY owner_type;
```

## Indexes
- **created_at**: [BTREE] Optimizes chronological file listings.
- **file_type**: [BTREE] Speeds up filtering for images vs documents.
- **owner_id** / **owner_type**: [BTREE] The primary indexes for polymorphic lookups.
