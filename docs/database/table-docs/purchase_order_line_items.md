# `purchase_order_line_items`

## Searchable Aliases
bought items, po components, procurement list, ordered parts, incoming stock items

## Description
The `purchase_order_line_items` table contains the specific itemized requirements for a Purchase Order. Each record represents a unique SKU being procured from a vendor, detailing the quantity, unit price, and fulfillment progress. 

This table is the primary input for the **Receiving** department and the **Landed Cost** calculations, as it tracks exactly how much of each item has arrived versus what is still pending.

## ⚙️ The Fulfillment & Costing Workflow
1.  **Line Creation**: A SKU is added to a PO with an `ordered_quantity` and a negotiated `price`.
2.  **Unit Conversion**: If the vendor sells in "Cases" but the business stocks in "Units," the `coefficient` (e.g., 12) and `uom_name` are used to translate the quantity for the warehouse.
3.  **Partial Receiving**: As stock arrives, the `received_quantity` is updated incrementally. The system compares this to the original `quantity` to identify "Backorders."
4.  **Landed Cost Rollup**: The `total_amount` for the line is calculated as: `(Quantity * Price) + Tariff + Overhead + Tax - Discount`.

## ⚠️ SQL-Critical Behaviors
- **Backorder Detection**: A line-item is considered "Open" as long as `received_quantity < quantity`. Fully fulfilled lines drive the transition of the parent PO to the `RECEIVED` status.
- **Staging Logic**: The `staged_quantity` identifies units that have arrived but are reserved ("Staged") for a specific production job or sales order before they are officially put away in a bin.
- **Required By Timing**: The `required_by` (Epoch) date on the line may differ from the header, allowing for staggered delivery schedules on large complex orders.

## Columns (33 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the procurement. |
| purchase_order_id | uuid | no | — | Link to the parent header in `purchase_orders.id`. |
| vending_id | uuid | no | — | Link to the specific vendor-sku relationship in the `vending` table. |
| item_store_id | uuid | no | — | Link to the internal branch-SKU in `item_stores.id`. |
| item_name | text | no | — | **Denormalized Name**: Display name of the item for the printed PO. |
| item_no | text | no | — | **Denormalized SKU**: The code of the item. |
| item_description | text | no | — | Technical description of the part. |
| quantity | numeric(12,2) | no | — | **Goal Quantity**: Total number of units ordered from the vendor. |
| price | numeric(12,2) | no | — | **Unit Cost**: The negotiated price per unit. |
| staged_quantity | numeric(12,2) | no | — | **Reservation Count**: Quantity physically in the building but not yet available for general sale. |
| received_quantity | numeric(12,2) | no | — | **Fulfillment Count**: Total quantity physically received to date. |
| lead_time | int4 | yes | — | The vendor's promised delivery time (in days) for this specific item. |
| uom_id | uuid | no | — | Link to the Unit of Measure definition (`uoms.id`). |
| coefficient | numeric(12,2) | no | — | The multiplier used to convert purchase units to stock units. |
| uom_name | text | no | — | Human-readable name of the purchase unit (e.g., "Box"). |
| tariff_amount | numeric(12,2) | no | — | Import or specialized duty fees for this SKU. |
| is_active | bool | no | — | Status flag. |
| required_by | int8 | yes | — | The specific deadline for this SKU (Epoch). |
| creator_id | uuid | no | — | The user who added this line item. |
| taxable | bool | no | — | If `true`, sales tax is calculated on this line. |
| tax_rate | numeric(12,2) | no | — | The percentage of tax applied to this item. |
| tax_amount | numeric(12,2) | no | — | The calculated tax dollar amount for the whole line. |
| discount_amount | numeric(12,2) | no | — | Flat dollar amount deducted from the line total. |
| overage | numeric(12,2) | no | — | Cost associated with slight over-delivery (e.g., shipping 102 units for an order of 100). |
| discount_rate | numeric(12,2) | no | — | Percentage discount for this specific SKU. |
| overhead | numeric(12,2) | no | — | Additional handling or landing fees for this specific line. |
| total_amount | numeric(12,2) | no | — | **Landed Total**: The final dollar impact of this item on the PO. |
| tariff_rate | numeric(12,2) | no | — | Import tariff percentage applied to this line when `tariffable`. |
| tariffable | bool | no | — | If `true`, tariffs are applied to this line. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| purchase_order_id | purchase_orders | id | cascade |
| vending_id | vending | id | cascade |
| item_store_id | item_stores | id | cascade |
| uom_id | uoms | id | set null |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| receive_line_items | purchase_order_line_item_id | Tracks specific arrivals against this line. |

## Common Query Patterns
```sql
-- Find all partially received items (Backorders)
SELECT item_no, item_name, (quantity - received_quantity) as pending 
FROM purchase_order_line_items 
WHERE received_quantity > 0 AND received_quantity < quantity;

-- Calculate the total value of stock currently "In-Transit" from vendors
SELECT SUM((quantity - received_quantity) * price) 
FROM purchase_order_line_items 
WHERE received_quantity < quantity;
```

## Indexes
- *Uses 6 btree indexes including `item_store_id`, `price`, `purchase_order_id`, and `quantity` to drive procurement and warehouse reporting.*
