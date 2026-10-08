# `shipment_checklists`

## Searchable Aliases
packing verification, shipping QC, pre-shipment audit, loading protocols

## Description
The `shipment_checklists` table is a **Junction Entity** that governs the Quality Control (QC) process for outbound logistics. It links a specific physical unit inside a parcel (`shipment_line_item_id`) to the technical or packaging requirements (`checklist_item_id`) it must satisfy before it is cleared for dispatch.

This table is the source of truth for the "Checklist Progression" logic in the warehouse, ensuring that complex technical equipment is inspected and verified against pre-defined standards before leaving the premises.

> [!IMPORTANT]
> **No `store_id` Column**: This is a pure junction table with no direct tenant scope. Tenant isolation is inherited by joining through `shipment_line_items` (which carries a `store_id`). Do not attempt to filter this table directly by branch.

## ⚙️ The Quality Control Workflow
1.  **Requirement Mapping**: When a shipment is created, the system identifies the necessary QC steps based on the item type (e.g., "Calibration Check" for electronics).
2.  **Inspection**: Warehouse clerks or technical inspectors perform each task.
3.  **Verification**: A record is created in this table for every successfully completed checklist item for that specific physical unit.
4.  **Shipment Release**: Once all mandatory `shipment_checklists` records are present for a line item, its `checklist_progress` is updated, and the parcel is cleared for carrier pickup.

## ⚠️ SQL-Critical Behaviors
- **Granular Proof**: This table provides the individual proof-of-inspection for every step. It allows managers to see *Exactly* which QC steps were performed for a specific serial number.
- **Relational Anchor**: It connects the logistics domain (`shipment_line_items`) to the structural logic domain (`checklist_items`), maintaining the integrity of the business's technical standards.

## Columns (5 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| shipment_line_item_id | uuid | no | — | Link to the specific physical asset/unit being inspected. |
| checklist_item_id | uuid | no | — | Link to the specific QC requirement being fulfilled. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| shipment_line_item_id | shipment_line_items | id | cascade |
| checklist_item_id | checklist_items | id | cascade |

## Common Query Patterns
```sql
-- Count completed QC steps for a specific physical unit in a shipment
SELECT COUNT(*) 
FROM shipment_checklists 
WHERE shipment_line_item_id = '<uuid>';

-- Verify if a specific mandatory checklist item has been completed for an order
SELECT id 
FROM shipment_checklists 
WHERE shipment_line_item_id = '<uuid>' 
  AND checklist_item_id = '<qc_rule_uuid>';
```

## Indexes
- *Relies on standard Primary Key and Foreign Key constraints for relational consistency.*
