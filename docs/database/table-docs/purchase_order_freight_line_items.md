# `purchase_order_freight_line_items`

## Searchable Aliases
procurement shipping costs, po freight, inbound transport fees, delivery surcharges

## Description
The `purchase_order_freight_line_items` table is the **Outbound Logistics Ledger** for the Purchasing domain. It itemizes the shipping, handling, and freight costs associated with a specific **Purchase Order** (PO) sent to a vendor.

Unlike sales freight, which is what the *customer* pays us, this table records the freight costs that *we* must pay the vendor or a third-party carrier to fulfill the procurement.

## ⚙️ The Purchasing Freight Workflow
1.  **Allocation**: During PO creation, a buyer identifies that the shipment will incur freight charges.
2.  **Service Selection**: The user selects a `carrier_id` and a `shipping_service_type_id` (e.g., "FedEx - Ground").
3.  **Cost Recording**: The `price` of the shipping service is recorded as a separate line item to ensure accurate "Landed Cost" calculations for the inventory.
4.  **Audit Trail**: The `purchase_order_id` link ensures that all transport costs are reconciled against the correct procurement contract.

## ⚠️ SQL-Critical Behaviors
- **Landed Cost Intelligence**: By separating `price` (freight) from the item cost, the system can calculate true inventory valuation.
- **Reference Integrity**: The `carrier_id` links directly to the master `carriers` table, providing technical visibility into vendor-provided transport.
- **Soft Deletion**: The `is_active` flag allows for the removal of freight lines if shipment terms change before final receipt.

## Columns (10 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch paying for the freight. |
| purchase_order_id | uuid | no | — | Link to the parent `purchase_orders.id`. |
| price | numeric(12,2) | no | — | **The Cost**: The dollar amount charged for the freight. |
| description | text | yes | — | Human-readable notes (e.g., "Fuel Surcharge"). |
| carrier_id | uuid | yes | — | Link to `carriers.id` identifying the logistics provider. |
| shipping_service_type_id | uuid | yes | — | Link to the specific service level (e.g., Express). |
| is_active | bool | no | true | Status toggle. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| purchase_order_id | purchase_orders | id | cascade |
| carrier_id | carriers | id | set null |
| store_id | stores | id | cascade |

## Common Query Patterns
```sql
-- Find the total freight spend for a specific Purchase Order
SELECT SUM(price) 
FROM "purchase_order_freight_line_items" 
WHERE purchase_order_id = '<uuid>' AND is_active = true;

-- Analyze shipping costs by carrier
SELECT c.name, SUM(f.price) 
FROM "purchase_order_freight_line_items" f
JOIN carriers c ON f.carrier_id = c.id
GROUP BY c.name;
```

## Indexes
- *Uses standard PK/FK constraints to support rapid logistics cost reporting.*
