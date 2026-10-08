# `boms`

## Searchable Aliases
assembly, blueprint, bill of materials, master list, design, engineering

## Description
The `boms` (Bill of Materials) table serves as the master "Recipe" for manufactured products and assemblies. It defines the structural relationship between a finished product and the specific components required to build it. 

Because engineering designs evolve over time, the **Lyndom** (the current PostgreSQL ERP) system allows for multiple versions of the same BOM, using a combination of `revision` codes and the `current` flag to determine which recipe is active in the production department.

## ⚙️ The Manufacturing & Versioning Workflow
1.  **Assembly Blueprint (`boms`)**: A header is created for a finished product (e.g., "Main Control Panel"). This header acts as a versioned container (`Revision A`).
2.  **Material Listing (`bom_records`)**: Multiple component lines are linked to the header. For Revision A, you might assign 10 silver screws.
3.  **The "Frozen" Revision**: To ensure historical accuracy, **you do not edit a used BOM**. Instead, if you switch to gold screws, you create a new `boms` record (`Revision B`) and assign it a new set of `bom_records`.
4.  **BOM Explosion**: When a Manufacturing Job is created, the system "Explodes" the `current` BOM, multiplying the `bom_records.quantity` by the total units being built to generate a warehouse picking list.

## ⚠️ SQL-Critical Behaviors
- **One-to-Many Bridge**: One `boms.id` typically links to 5–50 `bom_records.id` entries. Deleting a BOM header will cascade and remove all its component records.
- **The "Current Gold Standard"**: Only one revision per SKU should have `current = true`. This is the one used by the "Explosion" logic for all new production orders.
- **Matrice Scaling**: If `is_matrice = true`, the quantities in `bom_records` are treated as variables that the logic engine can scale based on custom engineering inputs (e.g., more cables required if the customer picks "Extra Tall Enclosure").

## Columns (15 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of initial design registration. |
| updated_at | timestamptz | no | — | Last modification to the recipe or header. |
| name | text | no | — | Short identifier for the BOM. |
| revision | text | no | — | **Engineering Version**: Alphanumeric code (e.g., `A`, `B`, `NR`) tracking design iterations. |
| description | text | no | — | Detailed notes on the purpose or changes in this revision. |
| is_active | bool | no | true | Global status flag. If `false`, the recipe is discontinued. |
| cost | numeric(12,2) | no | — | **Rollup Cost**: The total material cost of all sub-components. |
| current | bool | no | false | **The Production Standard**: If `true`, this version is used for all new manufacturing jobs. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this manufacturing recipe. |
| item_store_id | uuid | no | — | The specific SKU (`item_stores.id`) produced by this BOM. |
| record_count | numeric(12,2) | no | — | The number of component lines defined in this recipe. |
| note | text | yes | — | Internal engineering or assembly notes. |
| is_matrice | bool | no | false | **Parametric Template**: If `true`, the BOM allows for variable component quantities. |
| creator_id | uuid | no | — | The engineer or administrator who defined the recipe. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| item_store_id | item_stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| bom_records | bom_id | The specific component line items for this recipe. |

## Common Query Patterns
```sql
-- Find the current active recipe for a product
SELECT name, revision, cost 
FROM boms 
WHERE item_store_id = '<uuid>' AND current = true;

-- List historical revisions to track design evolution
SELECT revision, created_at, description 
FROM boms 
WHERE item_store_id = '<uuid>' 
ORDER BY created_at DESC;
```

## Indexes
- *Uses standard PK/FK constraints for relational integrity.*
