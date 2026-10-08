# `item_store_variants`

## Searchable Aliases
product variations, sku options, item models, color/size variants

## Description
The `item_store_variants` table is a junction that assigns a specific value to a commercial variation for a **Branch SKU**. While the `variants` table defines the options (e.g., "Color: Red, Blue"), this table records the selection for a particular item listing (e.g., Item X is "Red"). This facilitates the creation of unique SKU identities based on commercial features like finish, color, or material.

## ⚠️ SQL-Critical Behaviors
- **SKU Identity**: The combination of an `item_id` and its records in this table defines a unique commercial entity at the branch level.
- **Sales Integration**: When an item is added to a quote, these variants ensure the customer receives the exact commercial version they selected.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| item_store_id | uuid | no | — | Foreign key to `item_stores.id`. |
| variant_id | uuid | no | — | Foreign key to `variants.id`. |
| variant_name | text | no | — | Denormalized name of the variation (e.g., "Color"). |
| value | text | no | — | The chosen value (e.g., "Red"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| item_store_id | item_stores | id | cascade |
| variant_id | variants | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Find all variant selections for a specific SKU
SELECT variant_name, value 
FROM item_store_variants 
WHERE item_store_id = '<sku_uuid>';
```

## Indexes
- *Uses default PK and FK constraints.*
