# `uoms`

## Searchable Aliases
units of measure, quantity types, measurement units, billing increments

## Description
The `uoms` (Units of Measure) table manages how quantities are counted, packaged, and converted for specific items. Rather than using global units, this ERP scopes UOMs to individual `item_store_id` records, allowing for granular control over how different products are handled. For any given item, there is exactly one "Main" unit (the base unit of measure) and potentially multiple secondary units (e.g., "Pair", "Box", "Roll") which are related to the main unit via a numeric `coefficient`. This ensures the system can accurately calculate stock levels across different buying and selling units. Examples of actual values include: `Each` (standard base) and `Pair` (coefficient of 2.00).

## ⚠️ SQL-Critical Behaviors
- **Item-Specific Logic**: Queries for an item's quantity should always resolve to its `is_main = true` unit to ensure consistency.
- **Conversion Math**: The `coefficient` represents the multiplier relative to the main unit. Example: If the Main unit is `Piece` and a `Box` unit has a coefficient of `10.00`, then 1 Box = 10 Pieces.
- **Tenant & Item Isolation**: UOMs are strictly bound to both a `store_id` (for multi-tenancy) and an `item_store_id` (for product specificity).

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| store_id | uuid | no | — | Foreign key to `stores.id`. |
| name | text | no | — | Display name. Examples of actual values include: `Each`, `Pair`. |
| coefficient | numeric(12,2) | no | 1 | The multiplier relative to the main unit (e.g., 2.00 for a Pair). |
| is_main | bool | no | false | If `true`, this is the base unit used for core inventory balances. |
| is_active | bool | no | true | Status flag. Filter `WHERE is_active = true`. |
| item_store_id | uuid | no | — | Foreign key to `item_stores.id`. |
| is_default | bool | no | false | If `true`, this unit is pre-selected in purchasing or sales forms. |
| creator_id | uuid | no | — | The user who registered this unit. |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| store_id | stores | id | cascade |
| item_store_id | item_stores | id | cascade |
| creator_id | users | id | cascade |

### Referenced By (FK In)
| Table | Column | Meaning |
|-------|--------|---------|
| sales_order_line_items | uom_id | The unit used for a specific line in a sales order. |
| purchase_order_line_items | uom_id | The unit used for a specific line in a purchase order. |

## Common Query Patterns
```sql
-- Convert a secondary unit quantity to the main unit quantity
SELECT (quantity * u.coefficient) as base_quantity
FROM sales_order_line_items soli
JOIN uoms u ON soli.uom_id = u.id;

-- Find the default buying/selling unit for a specific item listing
SELECT name FROM uoms WHERE item_store_id = '<uuid>' AND is_default = true;
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| created_at | btree | Sorting by registration date. |
| is_active | btree | Filtering active units. |
| is_main | btree | Quick lookup for the base unit of an item. |
| item_store_id | btree | Finding all valid units for a specific product. |
| name | btree | Text search/filtering. |


