# `affected_components`

## Searchable Aliases
parts, components, impacted, hardware, assembly, modules, repairs

## Description
The `affected_components` table is the **Part Swap History** for the **Lyndom** (the current PostgreSQL ERP) system. It records exactly what happens to physical components when a machine is repaired or upgraded.

Whenever a technician touches a part inside a machine (a `unit`), they use this table to document the "Result": Did they put in a new part? Did they throw away an old part? Or did they fix a part that was already there? This provides a permanent record of how the internal "DNA" of the machine has changed since it first left the factory.

## ⚙️ The Part Swap Workflow (The Story of a Repair)
1.  **The Interaction**: A technician opens a machine to perform a repair or maintenance.
2.  **The Old Part (Removal)**: If they take out a failed component, they log its serial number here with a status of `REPLACED` (if they are keeping it for testing) or `DISCARDED` (if it is headed for the trash).
3.  **The New Part (Installation)**: If they install a replacement, they log the new part here as `NEW`.
4.  **The Fixed Part**: If they repair a part without removing it, they log it as `REPAIRED`.
5.  **BOM Synchronization**: This record links back to the machine's "Build List" (`unit_bom_records`), ensuring the system always knows exactly what is currently inside that specific machine serial number.

## ⚠️ SQL-Critical Behaviors
- **Strict Disposition Enum**: The `status` is enforced by a database-level `CHECK` constraint. No values outside the four defined fates (NEW, REPLACED, REPAIRED, DISCARDED) are permitted.
- **Identity Integrity**: The `inventory_item_id` provides the technical serial-number link to the physical piece of copper/silicon/steel being handled.
- **Audit Value**: This table is the primary data source for "Reliability Engineering" reports (e.g., "Which specific capacitor model is being DISCARDED most frequently in the field?").

## Columns (7 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the repair. |
| inventory_item_id | uuid | no | — | **The Physical Asset**: Link to the specific part in `inventory_items.id`. |
| job_record_id | uuid | yes | — | **Engineering Link**: The specific line in `unit_bom_records.id` affected by the failure. |
| status | text | no | — | **Technical Fate**: Must be `NEW`, `REPLACED`, `REPAIRED`, or `DISCARDED`. (Note: `DISCARDED` refers strictly to components thrown away during a machine repair event. For general warehouse inventory disposal or waste, use `goods_issues`). |
| creator_id | uuid | no | — | The technician or clerk who logged the part's fate. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| inventory_item_id | inventory_items | id | cascade |
| job_record_id | unit_bom_records | id | set null |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Reliability Audit: Find all DISCARDED components for a specific product category
SELECT ii.item_no, COUNT(ac.id) as scrap_count
FROM affected_components ac
JOIN inventory_items ii ON ac.inventory_item_id = ii.id
WHERE ac.status = 'DISCARDED'
GROUP BY ii.item_no
ORDER BY scrap_count DESC;

-- Unit History: List all components that have been REPLACED on a specific machine
SELECT ac.created_at, ii.serial_number, ac.status
FROM affected_components ac
JOIN inventory_items ii ON ac.inventory_item_id = ii.id
JOIN unit_bom_records ubr ON ac.job_record_id = ubr.id
WHERE ubr.unit_id = '<unit_uuid>' AND ac.status = 'REPLACED';
```

## Indexes
- *Relies on standard relational indexes on `inventory_item_id` and `job_record_id` for failure analysis auditing.*
