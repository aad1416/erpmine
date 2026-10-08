# `sales_order_freight_line_items`

## Searchable Aliases
shipping fees, delivery costs, sales freight, outbound transport charges

## Description
The `sales_order_freight_line_items` table manages the itemized shipping and handling charges applied to a Sales Order. Unlike internal logistics costs, this table represents the **Revenue** side of logistics—tracking exactly what the customer is being billed for transport services.

By separating freight into individual line items, the **Lyndom** (the current PostgreSQL ERP) system allows for complex shipping scenarios, such as split-shipments where multiple carriers or service levels (e.g., "Air" vs "Ground") are required for the same order.

## ⚙️ The Logistics Billing Workflow
1.  **Shipping Quote**: A salesperson or logistics coordinator adds a freight line to a Sales Order.
2.  **Service Mapping**: The charge is linked to a specific `carrier_id` (e.g., UPS) and `shipping_service_type_id` (e.g., "Next Day Air").
3.  **Financial Settlement**: The `price` here is rolled up into the `freight_cost` field on the parent `sales_orders` header for final invoicing.
4.  **Voiding**: If a shipment is canceled or the customer is granted "Free Shipping" after entry, the record is marked `is_active = false` to preserve the audit trail while removing the charge from the invoice total.

## ⚠️ SQL-Critical Behaviors
- **Revenue Recovery**: This table is the primary source for "Freight Recovery" reports—allowing the business to compare the price charged to the customer here against the actual vendor bills from the carriers.
- **Service Integration**: The link to `shipping_service_types` ensures that logistics reports can be filtered by service level (Expedited vs Standard).

## Columns (10 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the shipment. |
| sales_order_id | uuid | no | — | Link to the parent contract in `sales_orders.id`. |
| price | numeric(12,2) | no | — | **Customer Charge**: The dollar amount the client pays for this shipping service. |
| description | text | yes | — | Human-readable name of the charge (e.g., "LTL Freight", "Courier Fee"). |
| carrier_id | uuid | yes | — | Link to `carriers.id` identifying the transport company. |
| shipping_service_type_id | uuid | yes | — | Link to `shipping_service_types.id` (e.g., "Ground", "Air"). |
| is_active | bool | no | true | Status flag. If `false`, the freight charge is void. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| sales_order_id | sales_orders | id | cascade |
| carrier_id | carriers | id | set null |
| shipping_service_type_id | shipping_service_types | id | set null |

## Common Query Patterns
```sql
-- Calculate the total freight revenue for a specific branch
SELECT SUM(price) 
FROM sales_order_freight_line_items 
WHERE store_id = '<uuid>' AND is_active = true;

-- List all "Next Day Air" freight charges that are still pending fulfillment
SELECT f.price, s.number
FROM sales_order_freight_line_items f
JOIN sales_orders s ON f.sales_order_id = s.id
WHERE f.shipping_service_type_id = '<air_service_uuid>' 
  AND s.status != 'SHIPPED';
```

## Indexes
- *Relies on standard relational indexes for document generation.*
