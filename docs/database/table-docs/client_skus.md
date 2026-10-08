# `client_skus`

## Searchable Aliases
customer part numbers, cross-reference, client sku, mappings, external codes

## Description
The `client_skus` table provides a mapping layer for B2B relationships. Customers often use their own internal part numbers (SKUs) to refer to products sold by **Lyndom**. This table allows the ERP to store those cross-references, ensuring that transactional documents like Invoices, Packing Slips, and Quotes display the customer's preferred item number alongside or instead of the internal Lyndom SKU. Examples of actual values include `sku test` and `OEA Barron`.

## ⚠️ SQL-Critical Behaviors
- **Document Localization**: When generating a Sales Order or Invoice for a specific `client_id`, the system should join this table to retrieve the "Client Part Number" for display.
- **Order Entry**: Allows users to search for or import orders using the customer's own part numbers, which are then resolved to Lyndom's `item_store_id`.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| client_id | uuid | no | — | Foreign key to `clients.id`. |
| item_store_id | uuid | no | — | Foreign key to `item_stores.id`. |
| item_name | text | yes | — | The name the client uses for this item. |
| item_no | text | no | — | ⚠️ **Client SKU**: The part number used by the customer. Examples of actual values include: `OEA Barron`, `sku test`. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| client_id | clients | id | cascade |
| item_store_id | item_stores | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find the client's part number for a specific item we sold them
SELECT item_no, item_name 
FROM client_skus 
WHERE client_id = '<client_uuid>' AND item_store_id = '<sku_uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*
