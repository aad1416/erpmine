# `vending_cost`

## Searchable Aliases
vending machine finance, dispensed item costs, automation pricing

## Description
The `vending_cost` table acts as the historical log of purchase prices for each vendor-item relationship. While the `vending` table stores the *current* quoted cost, this table creates an immutable record of what was actually paid (or quoted) during a specific transaction.

This provides the data foundation for **Vendor Price Analysis** and **Inflation Tracking**.

## ⚙️ The Cost Tracking Workflow
1.  **Sourcing Event**: A Buyer places a Purchase Order (`purchase_orders.id`) with a vendor.
2.  **Cost Capture**: The system identifies the unit cost for that specific SKU.
3.  **Archival**: A new record is created in this table, linking the transaction (`vending_id`) and the PO to the specific dollar amount.
4.  **Trend Analysis**: Engineering and procurement teams use these records to track price escalations and renegotiate contracts.

## ⚠️ SQL-Critical Behaviors
- **Transaction Linkage**: Every record is optionally tied to a `purchase_order_id`. If `NULL`, the record may represent a manual price update or a new formal quote from the supplier.
- **Audit-Only Logic**: These records are created automatically by the purchasing module. They serve as a read-only historical ledger for auditors.

## Columns (7 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Date the price record was logged. |
| updated_at | timestamptz | no | — | System metadata. |
| cost | numeric(12,2) | yes | — | **The Historical Price**: The actual unit cost paid during this transaction. |
| vending_id | uuid | no | — | Link to the specific vendor-item relationship in `vending.id`. |
| purchase_order_id | uuid | yes | — | The specific purchase order (`purchase_orders.id`) that generated this cost record. |
| creator_id | uuid | no | — | The user identity (Buyer) who processed the transaction. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| vending_id | vending | id | cascade |
| purchase_order_id | purchase_orders | id | set null |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Analyze the cost trend for a specific SKU over time
SELECT cost, created_at 
FROM vending_cost 
WHERE vending_id = (SELECT id FROM vending WHERE sku = 'VND-123' LIMIT 1)
ORDER BY created_at DESC;

-- Identify the last known purchase price from a PO
SELECT cost 
FROM vending_cost 
WHERE purchase_order_id = '<uuid>';
```

## Indexes
- *Uses standard PK/FK indexing to support rapid price-over-time trend reporting.*
