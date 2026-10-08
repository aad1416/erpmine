# `part_request_line_items`

## Searchable Aliases
requested parts, component needs, material requisitions, sub-assembly requests

## Description
The `part_request_line_items` table contains the SKU-level details for an internal materials requisition. While the header defines the purpose and requestor, these line items specify the exact components and quantities required from stock.

It serves as the digital "Pick List" for the warehouse team, tracking the gap between what was requested by the technician and what has physically been handed over (Issued) from inventory.

## ⚙️ The Fulfillment & Shortage Workflow
1.  **Requirement Entry**: The requestor adds multiple line items to a `part_request`, specifying the `quantity` needed.
2.  **Constraint Identity**: Each line links to a specific `item_store_id`, providing the warehouse with the exact technical SKU to pull.
3.  **Partial Issuance**: If the warehouse only has partial stock available, they record the actual quantity given in `issued_quantity`.
4.  **Balance Tracking**: Any line where `issued_quantity < quantity` represents an internal shortage that may block a manufacturing job or field repair.
5.  **Finalization**: Once `issued_quantity` matches the requested `quantity`, the line is considered fully satisfied.

## ⚠️ SQL-Critical Behaviors
- **Historical Snapshot**: The `item_no`, `item_name`, and `item_description` are captured at the time of the request. This ensures that the documentation of the build/repair remains technically accurate even if the item master is renamed or discontinued.
- **Shortage Reporting**: The delta between `quantity` and `issued_quantity` is the primary source for the "Internal Shortage Report" used by procurement to identify missed production targets.
- **Traceability Bridge**: These line items serve as the technical link between the overall "Need" and the final `goods_issue_line_items` (the consumption).

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch managing the requisition. |
| part_request_id | uuid | no | — | Link to the parent header in `part_requests.id`. |
| item_store_id | uuid | no | — | **The SKU**: Link to the branch definition of the requested part. |
| item_no | text | no | — | Denormalized SKU for rapid identification in pick-lists. |
| item_name | text | no | — | Denormalized name of the component. |
| item_description | text | no | — | Technical description captured for the picker. |
| quantity | numeric(12,2) | no | — | **Requested Amount**: The total count of items needed. |
| issued_quantity | numeric(12,2) | no | — | **Fulfilled Amount**: The count of items physically subtracted from stock. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| part_request_id | part_requests | id | cascade |
| item_store_id | item_stores | id | cascade |

## Common Query Patterns
```sql
-- Identify critical internal shortages: Items where requested quantity exceeds issued quantity
SELECT part_request_id, item_no, (quantity - issued_quantity) as shortage_amount
FROM part_request_line_items 
WHERE issued_quantity < quantity;

-- Audit: List all components requested for a specific production build (Part Request)
SELECT item_no, item_name, quantity 
FROM part_request_line_items 
WHERE part_request_id = '<uuid>';
```

## Indexes
- *Includes high-performance btree indexes on `part_request_id` and `item_store_id` for warehouse pick-list generation.*
