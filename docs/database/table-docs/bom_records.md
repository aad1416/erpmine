# `bom_records`

## Searchable Aliases
ingredients, parts list, components, bill of materials, materials, formula, blueprint details

## Description
The `bom_records` table is the **Component Itemization Ledger** for the **Lyndom** (the current PostgreSQL ERP) system. It defines the specific constituent parts (line items) that comprise a master `boms` blueprint.

This table utilizes a **Technical Snapshot Pattern**. When a component SKU is added to a Bill of Materials, its identity (name, number, and description) is persisted directly into this record as literal text. This ensures that the technical integrity of the assembly remains stable even if the master SKU in the catalog is renamed or modified years later.

## ⚙️ The Manufacturing & Itemization Workflow
1.  **Assembly Drafting**: An engineer selects a component (**`item_store_id`**) to be included in a BOM.
2.  **Snapshot Activation**: The system pull the current `item_name`, `item_no`, and `item_description` from the branch SKU and records them here.
3.  **Quantification**: The **`quantity`** required for a single unit of the assembly is defined.
4.  **Scaling Logic**:
    *   If **`fixed_quantity`** is `false`, the system scales the requirement by the production volume.
    *   If **`fixed_quantity`** is `true`, the amount is a constant "Setup" quantity regardless of batch size.
5.  **BOM Explosion**: When a Manufacturing Job is launched, the logic engine queries this ledger to generate the aggregate material list required for the floor.

## ⚠️ SQL-Critical Behaviors
- **Snapshot Sovereignty**: For manufacturing picking lists and engineering audits, utilize the **`item_name`** and **`item_no`** columns in *this* table. These represent the "Engineering Intent" at the time the revision was created.
- **Scaling Rule**: Calculated Requirement = `(quantity * build_count)` if `fixed_quantity` is `false`.
- **Relational Anchor**: This table is the "Child" of the `boms` table. Deleting a BOM header will cascade and purge all its associated records.

## Columns (14 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. Unique component line ID. |
| created_at | timestamptz | no | — | Record registration timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the assembly. |
| bom_id | uuid | no | — | Link to the parent header in `boms.id`. |
| item_store_id | uuid | no | — | **The Component**: Foreign key to `item_stores.id`. |
| quantity | numeric(12,2) | no | — | **Amount**: Units required per single build (subject to scaling). |
| item_name | text | no | — | **Snapshot**: Part Name at the time of engineering. |
| item_no | text | no | — | **Snapshot**: Part Number at the time of engineering. |
| item_description | text | no | — | **Snapshot**: Technical Specs at the time of engineering. |
| name | text | yes | — | Optional override label (e.g., "Internal Frame"). |
| note | text | yes | — | Assembly or substitution instructions. |
| fixed_quantity | bool | no | false | If `true`, the quantity is flat and does not scale with batch size. |
| creator_id | uuid | no | — | The engineer or user who added the component. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| bom_id | boms | id | cascade |
| item_store_id | item_stores | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- List the "As-Engineered" material list for a specific BOM
SELECT item_no, item_name, quantity, fixed_quantity 
FROM bom_records 
WHERE bom_id = '<uuid>';

-- Audit: Identify all assemblies that use a specific part number (Current and Historical)
SELECT b.name, b.revision 
FROM bom_records br
JOIN boms b ON br.bom_id = b.id
WHERE br.item_no = 'PART-10022' OR br.item_store_id = '<uuid>';
```

## Indexes
- **bom_id**: [BTREE] Primary optimization for BOM explosion and production planning.
- **item_store_id**: [BTREE] For engineering impact analysis and sourcing audits.
