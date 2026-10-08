# `unit_bom_records`

## Searchable Aliases
as-built components, serialized parts, specific unit ingredients, build history

## Description
The `unit_bom_records` table is the **As-Built Bill of Materials** for a specific physical machine. While the standard `bom_records` table defines a generic recipe, this table is the "Permanent Blueprint" of exactly what is inside a specific serial number (`unit_id`).

It provides deep technical and financial traceability, capturing the exact parts, the vendor purchase orders they originated from, and the specific labor/tariff overheads applied during the construction of that unique asset. This is the primary reference for Field Service technicians when identifying compatible replacement parts for repairs.

## ⚙️ The Configuration Continuity Workflow
1.  **Instantiation**: When a manufacturing job begins for a specific unit, the system clones the active template BOM into the `unit_bom_records` table.
2.  **Procurement Mapping**: As parts are pulled from stock, the system populates the `purchase_order_numbers` array, creating a permanent link between the physical asset and its procurement history.
3.  **WIP Tracking**: The `issued_quantity` is updated as parts are physically "consumed" by the technician on the shop floor.
4.  **Cost Rollup**: The `total_cost`, `item_overhead`, and `item_tariff` are calculated for every line item, which then rolls up into the master `units.initial_valuation`.
5.  **Service Baseline**: Once the machine is in the field, this table becomes the "Source of Truth" for its internal configuration, even the master template BOM is modified later.

## ⚠️ SQL-Critical Behaviors
- **Deep Traceability**: The `purchase_order_numbers` JSONB is mission-critical for quality control. It allows the business to identify every unit in the field that contains a part from a specific vendor PO.
- **Multilevel Nesting**: By using the `parent_record_id`, the system can represent complex "Systems within Systems." An engine module might be a parent record, with individual pistons and rings as its children inside the same unit.
- **Historical Denormalization**: The `item_name`, `item_no`, and `item_description` are captured at the point of production to ensure the record remains readable even if the item master is deleted or renamed years later.

## Columns (23 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that built the unit. |
| parent_record_id | uuid | yes | — | **Hierarchy Link**: Self-reference to a parent assembly record in this table. |
| unit_id | uuid | no | — | **The Asset**: Link to the unique physical unit in `units.id`. |
| item_store_id | uuid | no | — | **The Part**: Link to the branch definition of the component. |
| quantity | numeric(12,2) | no | — | **Engineering Requirement**: The total count of this part required for the build. |
| effective_quantity | numeric(12,2) | no | 0 | The actual quantity calculated for the production run. |
| issued_quantity | numeric(12,2) | no | 0 | **Warehouse Consumption**: The count of parts physically picked for this unit. |
| item_name | text | no | — | Denormalized name of the part. |
| item_no | text | no | — | Denormalized SKU of the part. |
| item_description | text | no | — | Technical description of the part’s role in this build. |
| purchase_order_numbers | jsonb | no | `[]` | **The Audit Trail**: List of vendor POs which supplied these specific parts. |
| total_cost | numeric(12,2) | no | 0 | **Accumulated Cost**: The financial value of this part line in the unit valuation. |
| average_cost | numeric(12,2) | no | 0 | The average unit cost of the part at the point of consumption. |
| item_overhead | numeric(12,2) | no | 0 | Per-unit overhead applied to this specific part. |
| total_item_overhead | numeric(12,2) | no | 0 | Total overhead for the entire quantity of this part. |
| item_tariff | numeric(12,2) | no | 0 | Per-unit tariff/surcharge applied. |
| total_item_tariff | numeric(12,2) | no | 0 | Total tariff for the entire quantity. |
| external_key | text | yes | — | External reference ID for ERP integration. |
| is_active | bool | no | true | Global status flag. |
| creator_id | uuid | no | — | The user who registered the material consumption. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| unit_id | units | id | cascade |
| item_store_id | item_stores | id | cascade |
| parent_record_id | unit_bom_records | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Audit Failure Risk: Find all field units containing parts from a specific vendor PO
SELECT u.serial_number, ubr.item_no, ubr.item_name
FROM unit_bom_records ubr
JOIN units u ON ubr.unit_id = u.id
WHERE ubr.purchase_order_numbers ? 'PO-9022';

-- Reconstruct the full "As-Built" assembly list for a specific serial number
SELECT item_no, item_name, quantity, issued_quantity, total_cost
FROM unit_bom_records 
WHERE unit_id = '<uuid>'
ORDER BY parent_record_id NULLS FIRST;
```

## Indexes
- *Includes high-performance btree indexes on `unit_id` and `item_store_id` for technical audits.*
