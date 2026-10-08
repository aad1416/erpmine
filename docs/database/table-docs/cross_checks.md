# `cross_checks`

## Searchable Aliases
validations, error checking, consistency rules, audit flags, system alerts

## Description
The `cross_checks` table is the **Technical Validation Hub** of the **Lyndom** (the current PostgreSQL ERP) system. It manages the rules and metadata for comparing external engineering data—such as CAD exports, site-survey spreadsheets, or vendor catalog files—against internal technical standards.

By linking a specific uploaded document (`file_id`) to a named validation routine, the system provides engineers with an automated tool to identify incompatibilities, missing specs, or design-rule violations before a project enters production.

## ⚙️ The Engineering Validation Workflow
1.  **File Upload**: A user uploads a technical design file into the `files` table.
2.  **Audit Initiation**: A `cross_checks` record is created to define the scope of the audit (e.g., "Project Delta Compatibility Check").
3.  **Rule Definition**: The technical criteria for the check are defined in the `cross_check_applies_to` table (e.g., "Check all items where Voltage = 480V").
4.  **Reconciliation**: The system "cross-checks" the contents of the uploaded file against the rules and the internal product catalog.
5.  **Report Generation**: Discrepancies (missing items or invalid specs) are highlighted, allowing the engineer to correct the design file before proceeding.

## ⚠️ SQL-Critical Behaviors
- **File Linkage**: The `file_id` is mandatory. This table is strictly used for "Transactional Data Validation" against a specific static document.
- **Thematic Audits**: The `label` allows for the creation of standardized audit libraries (e.g., "UL Safety Standard Audit") used repeatedly for different project files.
- **Storefront Localization**: Cross-checks are segregated by `store_id`, ensuring that engineering standards for one branch (e.g., USA / 120V) are not accidentally applied to another (e.g., EU / 230V).

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| label | text | no | — | **Check Name**: (e.g., "Structural Load Validation 2026"). |
| file_id | uuid | no | — | **The Target File**: Link to the uploaded engineering/design file in `files.id`. |
| store_id | uuid | no | — | **Tenant ID**: The branch conducting the technical audit. |
| description | text | yes | — | Internal summary of the audit's purpose and technical scope. |
| creator_id | uuid | no | — | The engineer or quality manager responsible for the cross-check. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| file_id | files | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| cross_check_applies_to | cross_check_id | The individual technical spec criteria used to filter and validate the file contents. |

## Common Query Patterns
```sql
-- List all recent technical audits performed in a specific branch
SELECT label, created_at, description 
FROM cross_checks 
WHERE store_id = '<uuid>' 
ORDER BY created_at DESC;

-- Identify the design file associated with a specific cross-check audit
SELECT cc.label, f.name as filename
FROM cross_checks cc
JOIN files f ON cc.file_id = f.id
WHERE cc.id = '<uuid>';
```

## Indexes
- *Relies on standard relational indexes on `file_id` and `store_id` for document management.*
