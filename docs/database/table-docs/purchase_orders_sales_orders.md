# `purchase_orders_sales_orders`

## Searchable Aliases
back-to-back orders, drop shipments, order links, cross-referenced contracts

## Description
The `purchase_orders_sales_orders` table is a crucial **Junction Entity** that performs the "Hard Allocation" between supply and demand. It links specific vendor Purchase Orders directly to the customer Sales Orders that triggered them. 

This connection is the backbone of the **Drop-Ship** and **Just-In-Time (JIT)** procurement workflows, ensuring that incoming stock is never "Lost" in the general warehouse pool but is instead immediately earmarked for a specific customer commitment.

## ⚙️ The Allocation Workflow
1.  **Shortage Detection**: A customer order (SO) is placed for an item not in stock.
2.  **Back-to-Back Purchase**: The procurement team creates a PO specifically to fulfill that order.
3.  **The Binding**: A record is created in this table linking the `PO.id` and the `SO.id`.
4.  **Arrival Priority**: When the goods physically arrive at the dock, the receiving system uses this link to immediately mark the units as "Allocated" to the specific Sales Order, preventing them from being sold to a different customer.

## ⚠️ SQL-Critical Behaviors
- **One-to-Many / Many-to-Many**: A single large vendor PO might fulfill several different customer SOs. Conversely, one customer SO might require multiple POs from different vendors. This junction table manages that complexity.
- **Traceability Bridge**: This is the primary bridge for "Where is my order?" queries. It allows a customer service rep to jump from an open Sales Order directly to the specific vendor PO and tracking number that is holding it up.

## Columns (2 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| purchase_order_entity_id | uuid | no | — | Link to the specific vendor order in `purchase_orders.id`. |
| sales_order_entity_id | uuid | no | — | Link to the specific customer demand in `sales_orders.id`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| purchase_order_entity_id | purchase_orders | id | cascade |
| sales_order_entity_id | sales_orders | id | cascade |

## Common Query Patterns
```sql
-- Find which vendor PO is fulfilling a specific Customer Sales Order
SELECT purchase_order_entity_id 
FROM purchase_orders_sales_orders 
WHERE sales_order_entity_id = '<sales_order_uuid>';

-- Find all Customer Orders currently waiting for a specific Vendor shipment
SELECT sales_order_entity_id 
FROM purchase_orders_sales_orders 
WHERE purchase_order_entity_id = '<purchase_order_uuid>';
```

## Indexes
- *Uses a composite Primary Key across both UUIDs to ensure no duplicate allocations can be registered.*
