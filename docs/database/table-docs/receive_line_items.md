# `receive_line_items`

## Searchable Aliases
received items, incoming parts, stock intake, warehouse arrival, shipment receipt details

## Description
The `receive_line_items` table records the specific products and quantities that physically arrived during a receiving event. Every line item in a receiving voucher matches a corresponding requirement in a Purchase Order, providing the granular evidence needed to update stock levels and close out procurement contracts.

This table is the primary data source for identifying short-ships and vendor delivery accuracy.

## ⚙️ The Verification Workflow
1.  **Selection**: A warehouse worker selects an item on an incoming truck that matches a record in `purchase_order_line_items`.
2.  **Counting**: The worker physically counts the quantity and entering it in the `quantity` field.
3.  **Linking**: The system binds the arrival to the specific `purchase_order_line_item_id`. This connection is critical for ensuring that the correct SKU's "Outstanding Balance" is updated.
4.  **Stock Transformation**: Once the line is saved, the system generates a new record in `inventory_items`, transforming the "Receiving Info" into "Physical Stock on Hand."

## ⚠️ SQL-Critical Behaviors
- **Contract Fulfillment**: The `quantity` here is what was *actually found in the box*. If it is less than the PO requirement, the PO line remains open as a "Backorder."
- **Data Integrity**: The `item_name` is denormalized for historical accuracy. If the item's name changes in the master catalog later, the receiving voucher preserves the name as it appeared at the moment of delivery.

## Columns (11 Total)

| Column | Type | Nullable | Default | Business Description |
|--------|------|----------|---------|----------------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Record creation timestamp. |
| updated_at | timestamptz | no | — | Last modification timestamp. |
| store_id | uuid | no | — | **Tenant ID**: The branch that processed the receipt. |
| receive_id | uuid | no | — | Link to the parent voucher in `receives.id`. |
| purchase_order_line_item_id | uuid | no | — | **Source Link**: The specific line item on the PO that this delivery satisfies. |
| item_store_id | uuid | no | — | Link to the branch SKU in `item_stores.id`. |
| item_name | text | no | — | **Historical Name**: Name of the item as it was labeled at the time of receipt. |
| quantity | numeric(12,2) | no | — | **The Count**: Number of units physically received and placed in the bin. |
| is_active | bool | no | true | Status flag. |
| creator_id | uuid | no | — | The staff member who processed this specific line. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| receive_id | receives | id | cascade |
| purchase_order_line_item_id | purchase_order_line_items | id | cascade |
| item_store_id | item_stores | id | cascade |
| creator_id | users | id | cascade |

## Common Query Patterns
```sql
-- Track precisely what arrived in a specific Receiving Voucher
SELECT item_name, quantity 
FROM receive_line_items 
WHERE receive_id = '<uuid>';

-- Find all arrival dates for a specific Purchase Order Line
SELECT r.number, rli.quantity, r.received_at
FROM receive_line_items rli
JOIN receives r ON rli.receive_id = r.id
WHERE rli.purchase_order_line_item_id = '<uuid>'
ORDER BY r.received_at DESC;
```

## Indexes
- *Uses 6 btree indexes including `item_store_id`, `purchase_order_line_item_id`, and `receive_id` for rapid receiving auditing.*
