# `vending`

## Searchable Aliases
supplier mapping, procurement sources, vendor catalog, vendor pricing, sourcing

## Description
The `vending` table (Vendor-Specific Item Data) manages the relationship between a branch SKU and its various supply sources. While the `item_stores` table tracks the internal SKU, the `vending` table tracks the **Supplier's Version** of that product.

This table is critical for procurement automation, as it stores the vendor-specific part numbers, current purchase costs, and delivery lead times that the system uses to generate Purchase Orders.

## ⚙️ The Sourcing Workflow
1.  **Vendor Registration**: A vendor is linked to an internal item.
2.  **Sourcing Details**: The vendor's specific catalog number (`sku`), their quoted `cost`, and the expected delivery `lead_time` (in days) are recorded.
3.  **Preferred Selection**: One vendor is typically flagged as `preferred = true`. When the **Shortage Engine** (`required_items`) identifies a need for stock, it uses this preferred vendor's data to suggest where to buy.
4.  **Cost Evolution**: Changes to the vendor's price over time are historically tracked in the child `vending_cost` table.

## ⚠️ SQL-Critical Behaviors
- **Multi-Sourcing**: An item can have multiple `vending` records (one for each vendor that supplies it). This allows a buyer to compare costs and lead times between different suppliers before placing an order.
- **Data Parity**: The `vendor_name` is denormalized directly in this table. This ensures that sourcing reports and PO drafting screens remain highly performant without complex many-to-many joins.

## Columns (17 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Date the sourcing relationship was registered. |
| updated_at | timestamptz | no | — | Date of last price or lead time update. |
| store_id | uuid | no | — | **Tenant ID**: The branch that manages this vendor relationship. |
| vendor_id | uuid | no | — | Link to the global `vendors.id`. |
| vendor_name | text | no | — | **Denormalized Name**: Preferred supplier name for fast UI rendering. |
| item_store_id | uuid | no | — | Link to the internal branch SKU (`item_stores.id`). |
| is_active | bool | no | — | Global status. If `true`, represents an active supplier contract/agreement for this SKU. If `false`, vendor is not an approved source. |
| cost | numeric(12,2) | no | — | **Vendor Quoted Cost**: The price the supplier currently charges for a single unit. |
| lead_time | int4 | no | — | **Replenishment Delay**: The expected number of days between PO placement and Warehouse arrival. |
| sku | text | yes | — | **The Vendor's SKU**: The specific part number used in the vendor's own catalog. |
| preferred | bool | no | — | **The Primary Source**: If `true`, this vendor is the first choice for automated reordering. |
| creator_id | uuid | no | — | The procurement officer who negotiated or registered this sourcing link. |
| minimum_quantity_to_order | int4 | yes | — | Vendor-imposed minimum order quantity for this SKU. |
| lead_time_history | jsonb | no | — | jsonb array of `{mode, value, receiveId}` lead-time samples (days) observed at receiving. **Sparse**: non-empty on ~9 of ~32k rows — not usable as an as-at-PO lead-time source; use `lead_time`. |
| cost_history | jsonb | no | — | jsonb array of `{mode, value, purchaseOrderId}` unit-cost samples captured from purchase orders (~255 of ~32k rows non-empty). |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| vendor_id | vendors | id | cascade |
| item_store_id | item_stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| vending_cost | vending_id | Historical cost log for this specific vendor/item pair. |

## Common Query Patterns
```sql
-- Find all approved vendors for a specific internal SKU
SELECT vendor_name, cost, lead_time 
FROM vending 
WHERE item_store_id = '<uuid>' AND is_active = true;

-- List preferred vendors for a branch to assist in PO batching
SELECT vendor_name, sku, cost 
FROM vending 
WHERE store_id = '<uuid>' AND preferred = true;
```

## Indexes
- *Uses optimized btree indexes on `vendor_id`, `item_store_id`, and `preferred` to drive the automated Reorder Report.*
