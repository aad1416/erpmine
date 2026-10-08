# `rma_line_items`

## Searchable Aliases
returned parts, rma details, return items, defective components

## Description
The `rma_line_items` table contains the SKU-level itemization of a return authorization. Each record identifies a specific product, quantity, or unique physical unit that has been approved for return. 

This table bridges the gap between the "Authorization Header" and the "Physical Stock Ledger," providing the warehouse with the exact pick-list of what they should expect to find in the customer's incoming package.

## ⚙️ The Modular & Asset Workflow
- **Whole vs. Component**: The `whole_unit` flag is a technical discriminator. If `true`, the entire equipment assembly is being returned. If `false`, only a specific part or sub-component (e.g., a controller board) is being returned for repair or credit.
- **Mixed Logistics**: The table supports both **Serialized** items (linked through `unit_id`) and **Bulk** consumables (tracked via `quantity`). This provides the flexibility to handle high-value equipment and tiny replacement parts on the same RMA voucher.
- **Fulfillment Connection**: Every line is tied back to an `item_store_id`, ensuring that when the item is physically received, the correct SKU's "On-Hand" balance is incremented in the proper branch warehouse.

## ⚠️ SQL-Critical Behaviors
- **Denormalized Record**: The `item_name`, `item_no`, and `item_description` are captured at the moment the RMA is created. This ensures the historical record of *what was authorized* is preserved even if the product's catalog definition is updated later.
- **Verification Integrity**: Warehouse staff use these records to verify that the physical contents of a return package match what was legally authorized, preventing unauthorized "Blind Returns" from entering system stock.

## Columns (13 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the return line. |
| rma_id | uuid | no | — | Link to the parent authorization in `rma.id`. |
| item_store_id | uuid | no | — | Link to the branch product definition in `item_stores.id`. |
| item_name | text | no | — | **Historical Name**: Name of the part at the time of return authorization. |
| item_no | text | no | — | **Historical SKU**: The code of the part being returned. |
| item_description | text | no | — | Scope or technical condition of the returned item. |
| whole_unit | bool | no | — | **Technical Toggle**: If `true`, indicates the entire machine is returning. |
| unit_id | uuid | yes | — | **Unique Asset**: Link to the specific serialized unit serial number. |
| quantity | numeric(12,2) | no | — | **Authorized Count**: The number of units approved for return. |
| creator_id | uuid | no | — | The user who registered this specific line item. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| rma_id | rma | id | cascade |
| item_store_id | item_stores | id | cascade |
| unit_id | units | id | set null |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- List all serialized engines authorized for return but not yet received
SELECT item_name, unit_id 
FROM rma_line_items rl
JOIN rma r ON rl.rma_id = r.id
WHERE rl.whole_unit = true AND r.receive_date IS NULL;

-- Audit current volume of modular electronic repairs (Whole Unit = False)
SELECT item_name, COUNT(id) 
FROM rma_line_items 
WHERE whole_unit = false 
GROUP BY item_name;
```

## Indexes
- *Uses standard relational indexes to support rapid RMA auditing and document generation.*
