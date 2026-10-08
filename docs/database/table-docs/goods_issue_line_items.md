# `goods_issue_line_items`

## Searchable Aliases
issued items, component allocation, material list, parts withdrawal, stock consumption

## Description
The `goods_issue_line_items` table is the **Atomic Consumption Record** of the warehouse. It identifies the specific physical items that have been removed from inventory during a `goods_issue` event. 

By linking to the `inventory_item_id`, this table ensures that every part subtracted from stock is tracked with surgical precision—capturing the exact batch, serial number, and location from which the materials were retrieved.

## ⚙️ The Inventory Depletion Workflow
1.  **Selection**: A warehouse clerk selects the specific inventory records (`inventory_item_id`) that correspond to the approved part request.
2.  **Quantity Entry**: The clerk records the exact `quantity` physically taken from that inventory record.
3.  **Subtraction**: Upon saving, the system uses these line items to decrement the `quantity` and `available_quantity` in the `inventory_items` table.
4.  **Traceability Hook**: This record becomes the "Point of Origin" for any future cost-rollup to a Unit build or a Field Service repair.

## ⚠️ SQL-Critical Behaviors
- **Absolute Inventory Trigger**: These line items are the legal documentation of "Material Transformation" — the moment a part goes from "Stock" to "Consumption."
- **Precision Linking**: Unlike a high-level request, this table links to the specific **instance** of an item in the warehouse (the `inventory_item_id`).
- **Creator Accountability**: The `creator_id` represents the specific user who performed the digital "Out-Scan" of the goods.

## Columns (8 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch where the inventory exit occurred. |
| goods_issue_id | uuid | no | — | Link to the parent header in `goods_issues.id`. |
| inventory_item_id | uuid | no | — | **The Physical Asset**: Link to the specific record in `inventory_items.id`. |
| quantity | numeric(12,2) | no | 0 | **Amount Withdrawn**: The count of items removed from this specific inventory record. |
| creator_id | uuid | no | — | The user who registered the out-scan event. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| goods_issue_id | goods_issues | id | cascade |
| inventory_item_id | inventory_items | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| job_records_issue_line_items | issue_line_item_id | Links this withdrawal to a specific engineering BOM record (unit build). |

## Common Query Patterns
```sql
-- Audit: Find all serial numbers removed from stock in a specific Goods Issue
SELECT ii.serial_number, gil.quantity
FROM goods_issue_line_items gil
JOIN inventory_items ii ON gil.inventory_item_id = ii.id
WHERE gil.goods_issue_id = '<uuid>';

-- Velocity: Calculate total volume of items issued across a specific branch in the last 30 days
SELECT inventory_item_id, SUM(quantity) 
FROM goods_issue_line_items 
WHERE created_at > (NOW() - INTERVAL '30 days')
GROUP BY inventory_item_id;
```

## Indexes
- *Uses a high-performance btree index on `goods_issue_id` for document generation.*
