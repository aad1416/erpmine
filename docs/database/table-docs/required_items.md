# `required_items`

## Searchable Aliases
missing parts, procurement triggers, needed components, inventory gaps, stock requirements

## Description
The `required_items` table is the **Shortage Intelligence** engine of the ERP. It acts as a specialized data aggregator that identifies inventory deficits for a specific branch's SKUs. Instead of forcing a buyer to manually check every bin, this table centralizes all SKUs that have fallen below their `trigger_quantity` or have more `allocated` units than "On Hand."

> [!IMPORTANT]
> **No Direct `store_id` Column**: This table does **not** contain a `store_id`. Tenant isolation is inherited via the `item_store_id` foreign key. To scope a shortage report to a specific branch, you **must** join `item_stores` on `required_items.item_store_id = item_stores.id` and filter by `item_stores.store_id`.

It provides a prioritized "To-Buy" or "To-Build" list that directly links shortages back to the specific Sales Orders that require them.

## ⚙️ The Replenishment Workflow
1.  **Detection**: The system monitors inventory movements. When available stock dips below a threshold, a record is created/updated here.
2.  **Aggregation**: Shortages for the same SKU across multiple customer orders are summed into the `required_quantity`.
3.  **Traceability**: The IDs and Numbers of the affected Sales Orders are stored in the `sales_order_ids` JSONB, allowing a user to see exactly which customers are waiting for this item.
4.  **Procurement**: A Buyer uses this table as a "Launchpad" to generate new Purchase Orders.

## ⚠️ SQL-Critical Behaviors
- **Snapshot Data**: This table contains denormalized fields like `item_no` and `item_name`. This is intentional to ensure the Shortage Report remains high-performance even when processing thousands of records.
- **Trigger vs. Requirement**: The `required_quantity` is the *deficit*. If a SKU has a reorder point of 10 and we have 0 on hand, the `required_quantity` will likely be the `reorder_quantity` (the standard purchase lot size).
- **Unit Impact**: The `unit_info` JSONB stores details on specific serialized units that are blocked or "In Production," providing granular lifecycle context to the procurement team.

## Columns (20 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Date the shortage was first detected. |
| updated_at | timestamptz | no | — | Last time the shortage quantity was recalculated. |
| item_store_id | uuid | no | — | Link to the specific branch SKU in `item_stores.id`. |
| item_no | text | no | — | **Denormalized SKU**: The code of the required item. |
| item_name | text | no | — | **Denormalized Name**: The display name of the required item. |
| on_hand_quantity | numeric(12,2) | no | 0 | Current physical stock level in the warehouse. |
| on_order_quantity | numeric(12,2) | no | 0 | Quantity already in-flight from existing Purchase Orders. |
| allocated_quantity | numeric(12,2) | no | 0 | Quantity already committed to open Sales Orders but not yet picked. |
| reorder_quantity | numeric(12,2) | no | 0 | **Standard Lot Size**: The quantity typically ordered from the vendor. |
| trigger_quantity | numeric(12,2) | no | 0 | **Order Point**: The threshold that triggers this record's creation. |
| required_quantity | numeric(12,2) | no | 0 | **The Deficit**: The actual number of units needed to satisfy all commitments. |
| preferred_vendor_name | text | yes | — | Name of the primary supplier for this SKU. |
| preferred_vendor_id | uuid | yes | — | Link to `vendors.id` for fast PO generation. |
| uom_id | uuid | yes | — | The specific unit of measure for this shortage (e.g., "Box"). |
| uom_name | text | yes | — | Human-readable UOM name. |
| uom_coefficient | numeric(12,2) | yes | — | Conversion multiplier for the UOM. |
| sales_order_ids | jsonb | no | `[]` | **Audit Trail**: Array of `sales_orders.id` linked to this shortage. |
| sales_order_numbers | jsonb | no | `[]` | **Audit Trail**: Array of Human-readable order numbers for the UI. |
| unit_info | jsonb | no | `{}` | Technical details regarding the specific production units causing the demand. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| item_store_id | item_stores | id | cascade |
| preferred_vendor_id | vendors | id | set null |
| uom_id | uoms | id | set null |

## Common Query Patterns
```sql
-- Generate a High-Priority Shortage Report
SELECT item_no, required_quantity, preferred_vendor_name 
FROM required_items 
WHERE (on_hand_quantity + on_order_quantity) < allocated_quantity;

-- View which Sales Orders are the primary drivers of demand
SELECT item_no, sales_order_numbers 
FROM required_items 
WHERE required_quantity > 0;
```

## Indexes
- *Uses optimized btree indexes on `item_store_id` and `required_quantity` to facilitate real-time dashboard alerts.*
