# `shipments`

## Searchable Aliases
delivery vouchers, manifests, outbound shipments, packing slips, logistics events, transport docs

## Description
The `shipments` table is the **Logistics Voucher** for the physical movement of goods out of the warehouse. While a Sales Order represents the commercial agreement, a Shipment record represents the specific physical act of picking, packing, and dispatching items to a customer. 

This table manages the carrier integration, tracking numbers, and legal handover (FOB) of the products, acting as the bridge between the warehouse dock and the shipping carrier (e.g., FedEx, UPS).

## ⚙️ The Outbound Logistics Workflow
1.  **Release**: A Sales Order is cleared for shipping. A `shipments` record is created in `PENDING` status.
2.  **Picking/Packing**: Warehouse staff pack the items into boxes. Any additional weights or handling surcharges are recorded in `additional_weight` and `handling_charges`.
3.  **Carrier Pickup**: The `tracking_number` is assigned, and the `actual_ship_date` is recorded.
4.  **Finalization**: The status moves to `SHIPPED`. This trigger updates the inventory quantities and notifies the customer of the delivery progress.

## ⚠️ SQL-Critical Behaviors
- **Partial Shipments**: One Sales Order can have multiple linked `shipments`. This allows the system to ship in-stock items now and backordered items later.
- **FOB (Free On Board) Logic**: The `fob` column defines the legal point where the risk of loss passes to the customer. Common values like "Origin" mean the customer owns the goods the moment they leave our doc.
- **Quality Gate**: The `checklist_progress` (defaulting to `PENDING`) is a technical hook for future quality-control integrations, ensuring that complex technical equipment is inspected before dispatch.
- **Status Enum**: The fulfillment lifecycle is tracked via `status`. (Actual values include: `PENDING`, `PICKED`, `SHIPPED`, `CANCELLED`).

## Columns (21 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch shipping the goods. |
| number | text | no | — | **Shipment ID**: Human-readable serial number (e.g., SHIP-1022). |
| sales_order_id | uuid | no | — | Link to the parent contract in `sales_orders.id`. |
| date | int8 | no | — | The date the shipment was initiated (Epoch). |
| actual_ship_date | int8 | yes | — | The date the carrier physically took the goods (Epoch). |
| status | enum | no | — | **Logistics State**: (e.g., `PENDING`, `SHIPPED`). |
| checklist_progress | text | no | 'PENDING' | Status of the packing/quality checklist. |
| note | text | yes | — | Internal-only warehouse notes (e.g., "Fragile", "No Pallets"). |
| description | text | yes | — | General description of the package contents. |
| tracking_number | text | yes | — | The carrier's tracking ID for customer transparency. |
| carrier_id | uuid | yes | — | Link to the shipping company in `carriers.id`. |
| shipping_service_type_id | uuid | yes | — | Link to the service level in `shipping_service_types.id`. |
| shipping_price | numeric(12,2) | no | 0 | The raw cost of transport for this specific parcel. |
| handling_charges | numeric(12,2) | no | 0 | Surcharge for specialized packing or crating. |
| additional_weight | numeric(12,2) | no | 0 | Extra weight from packaging and pallets. |
| type | enum | no | 'NORMAL' | Indicates if this is a standard shipment or a `RUSH` order. |
| fob | text | no | '' | **Legal Handover**: Defines point of ownership transfer. |
| creator_id | uuid | no | — | The warehouse clerk who registered the shipment. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| sales_order_id | sales_orders | id | cascade |
| carrier_id | carriers | id | set null |
| shipping_service_type_id | shipping_service_types | id | set null |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| shipment_line_items | shipment_id | The specific items and quantities packed in this parcel. |

## Common Query Patterns
```sql
-- Find all shipped orders that do not have a tracking number recorded
SELECT number, sales_order_id 
FROM shipments 
WHERE status = 'SHIPPED' AND tracking_number IS NULL;

-- Audit current warehouse workload: Pick-list for today
SELECT number, sales_order_id, date 
FROM shipments 
WHERE status = 'PENDING' 
ORDER BY date ASC;
```

## Indexes
- *Includes a btree index on `created_at` for high-performance logistics auditing.*
