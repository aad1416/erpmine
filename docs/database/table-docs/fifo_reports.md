# `fifo_reports`

## Searchable Aliases
inventory valuation, first-in-first-out, stock value, cost accounting, financial audit

## Description
The `fifo_reports` table is the authoritative **Transaction Ledger for Inventory Valuation**. It implements the First-In-First-Out (FIFO) accounting principle, ensuring that the cost of goods sold is recorded based on the chronological entry of stock into the system. 

This table provides the line-item detail required for financial audits, tracking exactly when dollar value was added to or removed from the warehouse asset.

## ⚙️ The Valuation Workflow
1.  **Value Addition (ADD)**: When stock is received from a vendor (`purchase_orders`) or manufacturing, an `ADD` record is created with the specific unit `cost`. This becomes a "Cost Layer."
2.  **Value Reduction (REDUCE)**: When stock is sold (`goods_issues`) or consumed in a job, a `REDUCE` record is created. The system "consumes" the oldest available `ADD` layer to calculate the cost of that transaction.
3.  **Adjustment**: When a `cycle_count` occurs, the system creates an `ADD` or `REDUCE` entry to align the total dollar value with the new physical reality.

## ⚠️ SQL-Critical Behaviors
- **Immutable Financial Trail**: These records are the Basis for the **Cost of Goods Sold (COGS)**. They must never be manually altered.
- **Traceability**: The column `reference_number` acts as the cross-reference key to the physical paperwork (Vouchers, Invoices, Count Tags) associated with the value change.
- **Math Logic**: The `value` column represents the Unit Cost at that moment, which, when multiplied by `quantity`, represents the total financial impact of the event.

## Columns (20 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Timestamp of the valuation event. |
| updated_at | timestamptz | no | — | System metadata. |
| date | int8 | no | — | Epoch timestamp of the transaction date. |
| type | text | no | — | **Direction**: `ADD` (Stock In / Value Up) or `REDUCE` (Stock Out / Value Down). |
| item_store_id | uuid | no | — | The specific SKU listing being valuated. |
| receive_id | uuid | yes | — | The receiving event (`receives.id`) that added this value layer. |
| goods_issue_id | uuid | yes | — | The dispatch event (`goods_issues.id`) that consumed this value. |
| purchase_order_id | uuid | yes | — | The relevant procurement header for `ADD` events. |
| quantity | numeric(12,2) | no | — | **The Volume**: Number of units added or removed from the asset. |
| value | numeric(12,2) | no | — | **The Unit Cost**: The actual dollar value per unit for this transaction. |
| note | text | yes | — | Adjustment reasons or accounting notes. |
| reference_number | text | yes | — | **Omni-Reference**: The human-readable ID of the triggering document (receive/issue/cycle-count number, or e.g. `Initial Stock <sku>`). |
| purchase_order_number | text | yes | — | Human-readable PO number. |
| cycle_count_id | uuid | yes | — | The reconciliation event that caused a valuation adjustment. |
| rma_id | uuid | yes | — | Link to the RMA behind this entry, if any. |
| rma_number | text | yes | — | Human-readable RMA number, when the entry stems from a return. |
| rma_receive_id | uuid | yes | — | Link to the RMA receive voucher behind this entry, if any. |
| change_stock_id | uuid | yes | — | Link to the stock-change (manual adjustment) record behind this entry, if any. |
| is_imported | bool | no | — | If `true`, migrated from the legacy **Phocuss** (legacy MongoDB ERP) system. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| item_store_id | item_stores | id | cascade |
| receive_id | receives | id | set null |
| goods_issue_id | goods_issues | id | set null |
| purchase_order_id | purchase_orders | id | set null |
| cycle_count_id | cycle_counts | id | set null |

## Common Query Patterns
```sql
-- Calculate the total COGS for a specific SKU over a time period
SELECT SUM(quantity * value) 
FROM fifo_reports 
WHERE item_store_id = '<uuid>' AND type = 'REDUCE' 
  AND created_at BETWEEN '2025-01-01' AND '2025-12-31';

-- View the aging cost layers for a specific product
SELECT date, quantity, value 
FROM fifo_reports 
WHERE item_store_id = '<uuid>' AND type = 'ADD'
ORDER BY date ASC;
```

## Indexes
- *Relies on `item_store_id` and `type` for high-frequency financial reporting.*
