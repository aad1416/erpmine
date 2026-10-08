# `sales_order_line_items`

## Searchable Aliases
sold items, order details, sales components, customer order parts, fulfillment items

## Description
The `sales_order_line_items` table contains the itemized fulfillments for a Sales Order. Every record is a unique SKU commitment, defining the quantity, unit price, and physical fulfillment status. 

This table is the engine that drives the **Picking, Packing, and Shipping** workflows, as it tracks exactly how much of a customer's order has left the building versus what is still pending in the warehouse.

## ⚙️ The Fulfillment & Asset Workflow
- **Partial Shipment Engine**: The system manages backorders by comparing `quantity` (contracted) against `shipped_quantity` (moved out).
- **The Asset Trigger**: If `generate_unit = true`, the system automatically creates a record in the Physical Asset registry once the item is shipped. This ensures the part can be tracked for future field service and warranty repairs.
- **Packaging Constraints**: The `do_not_split` flag prevents the warehouse from shipping a partial quantity of a specific SKU if the items must arrive as a complete set.

## ⚠️ SQL-Critical Behaviors
- **Unit Transformation**: The `coefficient` and `uom_name` allow for Sales-to-Warehouse conversion (e.g., selling a "Pallet" but picking 50 "Cases").
- **Delivery Loop**: The `delivered_quantity` is updated via carrier tracking or manual input, providing a final audit match against the `shipped_quantity`.
- **Revenue Protection**: Like Quote lines, the `non_commissionable` flag ensures that sales reps are not paid for pass-through costs (fees/tariffs).
- **Formatting**: The `group` and `sort` columns ensure the customer's invoice matches the structure of the original proposal they approved.

## Columns (38 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the sale. |
| sales_order_id | uuid | no | — | Link to the parent header in `sales_orders.id`. |
| group | int4 | no | — | Section ID for grouping items on the final invoice. |
| sort | int4 | no | — | Display order within the group. |
| item_store_id | uuid | no | — | Link to the internal branch SKU in `item_stores.id`. |
| item_no | text | no | — | **Denormalized SKU**: The code as it appeared on the signed contract. |
| item_name | text | no | — | **Denormalized Name**: The display name of the item. |
| item_description | text | no | — | Technical description or scope of supply. |
| quantity | numeric(12,2) | no | — | **Ordered Quantity**: Total units contracted by the client. |
| shipped_quantity | numeric(12,2) | no | — | **Logistics Count**: Total units that have physically left the warehouse. |
| delivered_quantity | numeric(12,2) | no | — | **Handover Count**: Total units confirmed as received by the client. |
| taxable | bool | no | — | If `true`, sales tax is applied to this line. |
| price | numeric(12,2) | no | — | **Unit Sales Price**: The price agreed upon in the contract. |
| tax_rate | numeric(12,2) | no | — | The tax percentage applied to this SKU. |
| tariff_rate | numeric(12,2) | no | — | The tariff/duty percentage applied. |
| discount_rate | numeric(12,2) | no | — | Percentage discount for this specific line. |
| tax_amount | numeric(12,2) | no | — | Calculated dollar value of tax. |
| discount_amount | numeric(12,2) | no | — | Calculated dollar value of the discount. |
| total_amount | numeric(12,2) | no | — | **Line Total**: (Qty * Price) + Tax - Discount. |
| overage | numeric(12,2) | no | — | Margin surcharge for high-value SKU configurations. |
| tariff_amount | numeric(12,2) | no | — | Calculated dollar value of tariffs. |
| tariffable | bool | no | — | If `true`, tariffs are applied to this record. |
| non_commissionable | bool | no | — | If `true`, this line is excluded from rep commission totals. |
| is_active | bool | no | — | Status flag. |
| shippable | bool | no | — | If `true`, requires physical warehouse packaging and a `shipments` record. |
| do_not_split | bool | no | — | **Logistics Barrier**: If `true`, must be shipped in full (no partials). |
| uom_id | uuid | no | — | Link to the Unit of Measure definition (`uoms.id`). |
| coefficient | numeric(12,2) | yes | — | The multiplier used to convert sales units to stocking units. |
| uom_name | text | no | — | Human-readable name of the sales unit (e.g., "Pallet"). |
| generate_unit | bool | no | — | **Asset Flag**: If `true`, shipping this item creates a new physical asset for the client. |
| note | text | yes | — | Internal-only comments or installation instructions for the line. |
| creator_id | uuid | yes | — | The user who registered the line-item. |
| price_label | text | yes | — | Optional custom label for the price field. |
| dropship | bool | no | — | If `true`, this line ships directly from the vendor to the customer and never enters the warehouse. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| sales_order_id | sales_orders | id | cascade |
| item_store_id | item_stores | id | cascade |
| uom_id | uoms | id | set null |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| shipment_line_items | sales_order_line_item_id | Tracks the specific parcel allocations for fulfillment. |

## Common Query Patterns
```sql
-- Find all partially shipped items (Backorders) across the branch
SELECT item_no, item_name, (quantity - shipped_quantity) as backorder_qty 
FROM sales_order_line_items 
WHERE shipped_quantity > 0 AND shipped_quantity < quantity;

-- List all items awaiting final delivery confirmation
SELECT item_name, shipped_quantity, delivered_quantity 
FROM sales_order_line_items 
WHERE shipped_quantity > delivered_quantity;
```

## Indexes
- *Includes indexes on `item_store_id` and `sales_order_id` for rapid logistics reporting.*
