# `notes`

## Searchable Aliases
internal comments, sticky notes, reminders, annotations, record logs

## Description
The `notes` table is the **Polymorphic Annotation Hub** of the **Lyndom** (the current PostgreSQL ERP) system. It serves as a universal commenting engine that can be "attached" to almost any entity in the database (e.g., Sales Orders, Units, Clients, or Production Tasks).

By using a polymorphic `owner_type` strategy, this single table provides an unstructured communication layer across the entire ERP, allowing employees to capture human context, special instructions, or status updates that aren't represented by formal data fields.

## ⚙️ The Universal Commenting Workflow
1.  **Note Creation**: A user identifies a record that requires human context (e.g., a Sales Order with a complex delivery requirement).
2.  **Polymorphic Linking**: The ERP creates a record in this table. It stores the `owner_id` (the ID of the target record) and specifies the `owner_type` (e.g., `'sales_order'`).
3.  **Content Recording**: The `note` text is captured along with the `creator_id` of the author.
4.  **Display Logic**: When a user views the Sales Order, the application queries this table for all notes where `owner_id` matches the current record, presenting a chronological conversation or audit trail.

## ⚠️ SQL-Critical Behaviors
- **Entity Agnostic Architecture**: This table doesn't have Foreign Keys to specific tables like `sales_orders` or `units`. Instead, it uses a generic `owner_id` (UUID) and `owner_type` (String).
- **Tenant Privacy**: Even though notes are polymorphic, they are pinned to a `store_id`. This prevents "Note Leakage" between different branches of the company.
- **Permanent Audit**: Setting `is_active = false` allows for soft-deletion of notes, preserving the historical trail of internal communications for administrative review.

## Columns (10 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| subject | text | yes | — | **Note Heading**: Optional title or subject for the annotation. |
| note | text | no | — | **The Commentary**: The actual body of the internal note. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this internal comment. |
| owner_id | uuid | no | — | **Link Target ID**: The UUID of the record being annotated. |
| owner_type | text | no | — | **Link Target Type**: (e.g., `'sales_order'`, `'unit'`, `'client'`). |
| is_active | bool | no | true | Status flag. If `false`, the note is hidden from standard views. |
| creator_id | uuid | no | — | **The Author**: Link to the user who wrote the note. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| *Polymorphic* | *owner_id* | This table is queried by every module supporting the "Internal Notes" feature. |

## Common Query Patterns
```sql
-- Retrieve all internal conversation history for a specific Sales Order
SELECT created_at, note, creator_id 
FROM notes 
WHERE owner_id = '<so_uuid>' AND owner_type = 'sales_order' 
ORDER BY created_at ASC;

-- Audit: Find all notes created by a specific technician across the entire system
SELECT note, owner_type, created_at 
FROM notes 
WHERE creator_id = '<user_uuid>';
```

## Indexes
- *Relies on standard relational indexes on `owner_id` and `store_id` for document generation.*
