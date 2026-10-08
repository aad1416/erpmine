# `cross_check_applies_to`

## Searchable Aliases
validation rules, dependency mapping, rule scope, data integrity targets

## Description
The `cross_check_applies_to` table is the **Filter Logic Engine** for technical verification. It defines the specific technical criteria used to "cross-check" an uploaded design file against the internal product catalog. 

This table allows engineers to define surgical rules—such as "Only check items in the 'Transformers' category that have a 'Voltage' of '480V'"—to identify if a customer’s design file contains invalid technical configurations or unavailable items.

## ⚙️ The Technical Filtering Workflow
1.  **Rule Definition**: An engineer adds a record to this table, anchoring it to a master `cross_check_id`.
2.  **Targeting**: The engineer selects a `category_id` (The product family) and a physical `specification_id`.
3.  **Benchmark Assignment**: The target `value` and `unit` are recorded (e.g., "100", "Amps").
4.  **Automatic Sifting**: When the cross-check tool runs, it only analyzes the rows in the uploaded file that match these specific technical criteria.
5.  **Discrepancy Highlighting**: If a row in the file matches the criteria but does not exist in the **Lyndom** (the current PostgreSQL ERP) catalog, it is flagged for engineering review.

## ⚠️ SQL-Critical Behaviors
- **Specification Precision**: The table links to both the `specification_id` (Technical GUID) and denormalized `spec_name` (Human readability). This ensures that the validation rules remain audit-ready even if the catalog structure changes.
- **Parametric Filtering**: By storing the `value` and `unit` as text, the system can perform broad logical matching across diverse engineering data.
- **Integrity Anchors**: Every rule is tied to a `category_id`, preventing the system from cross-checking irrelevant gear (e.g., ensuring "Cable" rules aren't applied to "Enclosure" data).

## Columns (9 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| cross_check_id | uuid | no | — | Link to the parent audit header in `cross_checks.id`. |
| category_id | uuid | no | — | **The Scope**: The item category where this validation rule applies. |
| specification_id | uuid | no | — | Link to the technical characteristic in `specifications.id`. |
| spec_name | text | no | — | Denormalized name of the attribute (e.g., "Wattage"). |
| value | text | no | — | **The Benchmark**: The specific value being checked for in the file. |
| unit | text | no | — | The unit of measure for the benchmark value (e.g., "kW"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| cross_check_id | cross_checks | id | cascade |
| category_id | categories | id | cascade |
| specification_id | specifications | id | cascade |

## Common Query Patterns
```sql
-- List all technical rules applied to a specific Design Audit
SELECT spec_name, value, unit 
FROM cross_check_applies_to 
WHERE cross_check_id = '<uuid>';

-- Audit: Identify all cross-checks that included "Stainless Steel" as a material requirement
SELECT cc.label, ccat.value
FROM cross_check_applies_to ccat
JOIN cross_checks cc ON ccat.cross_check_id = cc.id
WHERE ccat.spec_name = 'Material' AND ccat.value = 'Stainless Steel';
```

## Indexes
- *Uses high-performance btree indexes on `cross_check_id`, `category_id`, and `specification_id` for automated file auditing.*
