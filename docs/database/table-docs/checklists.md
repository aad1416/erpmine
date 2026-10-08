# `checklists`

## Searchable Aliases
procedures, inspections, quality control, forms, audits, protocols

## Description
The `checklists` table serves as the **Template Registry** for Quality Control and Procedural Verification within the **Lyndom** (the current PostgreSQL ERP) ecosystem. Rather than storing individual inspection results, this table defines the *High-Level Blueprint* for a verification process (e.g., "Standard Electronics Inspection", "Final Packaging Audit").

These templates are instantiated into specific events like `shipment_checklists`, providing the business with a reusable engine for enforcing operational standards across various departments (Warehouse, Service, and Receiving).

## ⚙️ The Standardization Workflow
1.  **Template Creation**: A manager defines a new checklist (e.g., "Safety Verification").
2.  **Itemization**: Specific tasks are linked to this checklist via the `checklist_items` table.
3.  **Deployment**: When a physical action occurs (like shipping a specific category of item), the system pulls the relevant checklist blueprint to guide the operator.
4.  **Governance**: The `is_active` flag allows for the retirement of old procedures without losing the historical record of which template was used for past transactions.

## ⚠️ SQL-Critical Behaviors
- **Global vs. Local**: Checklists are linked to a specific `store_id`, allowing different branches to have specialized quality standards (e.g., a "Service Branch" vs. a "General Warehouse").
- **Visual Order**: The `order` column defines the primary sequence in which the templates are presented in the UI, helping organize the Quality Management system.

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this procedure template. |
| name | text | no | — | **Blueprint Name**: (e.g., "Pre-Delivery Inspection"). |
| description | text | yes | — | Detailed summary of the purpose of this checklist. |
| order | int4 | no | 0 | The sequence ID for display in the management UI. |
| is_active | bool | no | true | If `false`, this template is retired and cannot be used for new events. |
| creator_id | uuid | no | — | The user or manager who designed the template. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| checklist_items | checklist_id | The specific tasks/steps that make up this template. |

## Common Query Patterns
```sql
-- List all active inspection templates for a specific branch
SELECT name, description 
FROM checklists 
WHERE store_id = '<uuid>' AND is_active = true 
ORDER BY "order" ASC;

-- Audit: Who created our current Quality Control templates?
SELECT c.name, u.email 
FROM checklists c
JOIN users u ON c.creator_id = u.id;
```

## Indexes
- *Relies on standard relational indexes for template management.*
