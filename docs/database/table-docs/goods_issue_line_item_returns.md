# `goods_issue_line_item_returns`

## Searchable Aliases
returned materials, component returns, stock adjustments, issue reversal

## Description
The `goods_issue_line_item_returns` table manages the return of unused or excess physical material from the assembly line or field back to the warehouse. In many industrial workflows, more parts are "Issued" than are actually consumed (to prevent technical delays); this table is the mechanism for correcting the inventory balance after the work is finalized.

It ensures that the ERP reflects **Net Consumption**, rather than just gross issuance, providing the finance department with an accurate picture of actual material usage.

## ⚙️ The Inventory Reversal Workflow
1.  **Identification**: A technician completes a task and identifies parts that were withdrawn but not physically installed or used.
2.  **Return Entry**: The warehouse clerk creates a record in this table, specifically linking it to the original `goods_issue_line_item_id`.
3.  **Physical Inspection**: The clerk verifies the quantity and condition of the returned goods.
4.  **Stock Increment**: Upon saving, the system automatically increments the `quantity` and `available_quantity` for the affected record in the `inventory_items` table.
5.  **Cost Adjustment**: The accumulated `part_cost` on the parent `units` record is typically reduced by the value of these returned items.

## ⚠️ SQL-Critical Behaviors
- **Line-Level Symmetery**: Every return must point to a specific issuance line. This maintains a perfect "Paper Trail" for high-value components.
- **Zero-Sum Accuracy**: Without this table, the ERP would show inflated material costs for builds and deflated inventory stock levels.
- **Audit Gatekeeper**: The `creator_id` acts as the signature of the person responsible for restocking the warehouse shelf.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch receiving the return. |
| goods_issue_id | uuid | no | — | Link to the original header in `goods_issues.id`. |
| goods_issue_line_item_id | uuid | no | — | **Source Anchor**: The specific issuance line being reversed. |
| quantity | numeric(12,2) | no | 0 | **Return Amount**: The count of items being put back into stock. |
| creator_id | uuid | no | — | The user who registered the return/restock event. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| goods_issue_id | goods_issues | id | cascade |
| goods_issue_line_item_id | goods_issue_line_items | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Audit: List all returns for a specific large manufacturing build
SELECT gir.quantity, gi.number as issue_number
FROM goods_issue_line_item_returns gir
JOIN goods_issues gi ON gir.goods_issue_id = gi.id
WHERE gi.sales_order_id = '<uuid>';

-- Integrity Check: Ensure total returned quantity does not exceed original issued quantity
SELECT gil.id, gil.quantity as issued, SUM(gir.quantity) as total_returned
FROM goods_issue_line_items gil
JOIN goods_issue_line_item_returns gir ON gil.id = gir.goods_issue_line_item_id
GROUP BY gil.id, gil.quantity
HAVING SUM(gir.quantity) > gil.quantity;
```

## Indexes
- *Uses standard relational indexes on `goods_issue_id` and `created_at` for monthly inventory reconciliation.*
