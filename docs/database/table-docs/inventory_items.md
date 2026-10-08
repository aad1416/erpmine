# `inventory_items`

## Searchable Aliases
stock levels, physical inventory, quantity on hand, warehouse items, shelf life, bin location, stock tracking

## Description
The `inventory_items` table is the atomic registry for physical stock within the **Lyndom** (the current PostgreSQL ERP) system. While `item_stores` tracks the *idea* of a product at a branch, `inventory_items` tracks the **physical reality** on the shelf. 

It serves a dual purpose:
1.  **Individual Unit Tracking**: For items tracked by `SERIAL`, each record represents a unique physical unit with a specific `serial_number`.
2.  **Bulk Bin Tracking**: For items tracked by `QUANTITY`, each record represents a "lot" or "slot" of identical parts within a specific warehouse bin (`location_id`).

## ⚠️ SQL-Critical Behaviors
- **Quantity Accounting**: The total `quantity` is an aggregate of `available_quantity` (stock ready for sale/use) and `issued_quantity` (stock physically removed from the bin for a manufacturing job or shipment). 
- **Stock Sourcing**: Every record links back to either a **Purchase Order** (`purchase_order_id`) or a specific **Receiving Event** (`receive_id`), providing a complete audit trail from procurement to the shelf.
- **Location Strictness**: An inventory record is tied to a specific `location_id`. Moving stock between bins requires a transaction that updates this ID or archives the old record and creates a new one.
- **Serial Lookup**: The `serial_number` is indexed for fast lookups. This allows technicians to find exactly which warehouse slot contains a piece of equipment by scanning its manufacturer tag.

## Columns (24 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Date the stock was registered in the bin. |
| updated_at | timestamptz | no | — | Date of last movement or quantity adjustment. |
| store_id | uuid | no | — | **Tenant ID**: The branch that owns this physical stock. |
| item_store_id | uuid | no | — | Link to the branch-specific SKU definition. |
| location_id | uuid | yes | — | **The Bin**: Foreign key to `locations.id` indicating where the item is physically stored. |
| serial_number | text | yes | — | **Unique Identifier**: The internal or company-assigned serial number for the unit. |
| manufacturing_serial_number | text | yes | — | The Original Equipment Manufacturer (OEM) serial number. |
| extra_data | jsonb | yes | — | Extensible metadata (e.g., condition notes, hardware revisions). |
| cost | numeric(12,2) | no | — | **Valuation Cost**: The specific landed cost for these units (essential for FIFO). |
| purchase_order_id | uuid | yes | — | The procurement source (`purchase_orders.id`) for this stock. |
| receive_id | uuid | yes | — | The receiving event header that brought this item into the building. |
| receive_line_item_id | uuid | yes | — | The specific line on the receiving voucher. |
| creator_id | uuid | no | — | The employee who processed the receiving/stocking event. |
| cycle_count_id | uuid | yes | — | Most recent reconciliation event for this stock slot. |
| quantity | int4 | no | — | **Total Count**: The sum of all units (Available + Issued) in this record. |
| available_quantity | int4 | no | — | **Net Stock**: Units currently on the shelf and available for consumption. |
| issued_quantity | int4 | no | — | **Commitment Count**: Units currently removed from the bin for an active job/shipment. |
| external_unit_id | uuid | yes | — | Link to the counterpart unit record in the *selling* store for inter-store transfers. |
| rma_id | uuid | yes | — | Link to the RMA under which this unit was returned. |
| rma_receive_id | uuid | yes | — | Link to the RMA receive voucher that brought this unit back into stock. |
| rma_receive_line_item_id | uuid | yes | — | Link to the RMA receive line item for this unit. |
| change_stock_id | uuid | yes | — | Link to the stock-change (manual adjustment) record that created this unit, if any. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| item_store_id | item_stores | id | cascade |
| location_id | locations | id | set null |
| purchase_order_id | purchase_orders | id | set null |
| receive_id | receives | id | set null |
| receive_line_item_id | receive_line_items | id | set null |
| cycle_count_id | cycle_counts | id | set null |

## Common Query Patterns
```sql
-- Find exactly which bin contains a specific Serial Number
SELECT l.name, ii.quantity 
FROM inventory_items ii
JOIN locations l ON ii.location_id = l.id
WHERE ii.serial_number = 'SN-123456';

-- Calculate total available stock for a specific SKU across all bins
SELECT SUM(available_quantity) 
FROM inventory_items 
WHERE item_store_id = '<uuid>';
```

## Indexes
- *Uses 7 btree indexes including `item_store_id`, `location_id`, and `serial_number` to ensure millisecond-level stock lookups.*
