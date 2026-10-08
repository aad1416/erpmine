# `shipment_line_items`

## Searchable Aliases
packed items, manifested parts, shipping container details, delivery units

## Description
The `shipment_line_items` table is the granular record of the specific physical assets placed inside a shipment. In the **Lyndom** (the current PostgreSQL ERP) logistics engine, fulfillment is strictly **Serialized**. Each record in this table represents a single, unique unit of inventory (linked via `unit_id`) being dispatched to a customer.

Because the system tracks assets at the individual level, this table does not contain a "Quantity" column. Instead, shipping multiple units of the same SKU results in multiple records, each identifying a specific serial number.

## ⚙️ The Serialized Fulfillment Workflow
1.  **Selection**: A warehouse worker selects a specific physical asset (`unit_id`) from the shelf to fulfill a line item on a Sales Order.
2.  **Assignment**: The asset is linked to the `shipment_id` (the box/parcel) and the `sales_order_line_item_id` (the contract requirement).
3.  **Inspection**: The worker performs any required technical checks, updating the `checklist_progress` for that specific unit.
4.  **Traceability**: Once the shipment is finalized, the system uses these records to move the physical assets from "Warehouse Stock" to "Customer Field Unit" status.

## ⚠️ SQL-Critical Behaviors
- **1-to-1 Asset Rule**: Every record here is a unique physical item. To calculate the total count of a SKU in a shipment, you must `COUNT(*)` the records rather than summing a quantity column.
- **The Customer Bridge**: The `unit_id` linkage is critical. It provides the permanent legal proof of exactly which serial number was delivered to which client, essential for future warranty and maintenance claims.
- **Data Preservation**: The `item_name`, `item_no`, and `item_description` are denormalized from the master catalog at the moment of shipping to preserve the historical state of the asset.

## Columns (13 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch fulfilling the item. |
| shipment_id | uuid | no | — | Link to the parent parcel in `shipments.id`. |
| item_name | text | no | — | **Denormalized Name**: Name of the product as shipped. |
| item_no | text | no | — | **Denormalized SKU**: The code of the product. |
| item_description | text | no | — | Technical description of the specific asset. |
| item_store_id | uuid | no | — | Link to the internal branch product in `item_stores.id`. |
| unit_id | uuid | no | — | **The Physical Asset**: Link to the unique serialized unit in the inventory. |
| checklist_progress | text | no | — | Progression status of the technical inspection for this specific unit. |
| creator_id | uuid | no | — | The warehouse clerk who packed this item. |
| sales_order_line_item_id | uuid | no | — | **Contract Link**: The specific SO line this asset satisfies. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| shipment_id | shipments | id | cascade |
| item_store_id | item_stores | id | cascade |
| unit_id | units | id | cascade |
| sales_order_line_item_id | sales_order_line_items | id | cascade |

## Common Query Patterns
```sql
-- List all serialized assets (Serial Numbers) inside a specific shipment
SELECT item_name, unit_id, checklist_progress 
FROM shipment_line_items 
WHERE shipment_id = '<uuid>';

-- Verify which Sales Order a specific physical unit was shipped on
SELECT s.number, sli.item_no 
FROM shipment_line_items sli
JOIN shipments s ON sli.shipment_id = s.id
WHERE sli.unit_id = '<unit_uuid>';
```

## Indexes
- *Includes indexes on `shipment_id` and `created_at` for rapid fulfillment auditing.*
