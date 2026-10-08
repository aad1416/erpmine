# `item_store_specifications`

## Searchable Aliases
branch-specific specs, local item attributes, store product details

## Description
The `item_store_specifications` table stores technical values assigned to a specific **Branch SKU (Item-Store)**. While `item_specifications` define the "Blueprint" values at the master level, this table allows a store to have its own specific version of those specs or to define values for a configurable product. This is essential for manufactured equipment where the exact technical profile (e.g., Input Voltage: 208, Power Rating: 24) must be tracked per branch listing for accurate production and sales. Examples of actual values include `Input Voltage` (208), `Output Voltage` (480Y/277), and `Frequency` (50).

## ⚠️ SQL-Critical Behaviors
- **SKU-Level Overrides**: This table is the source of truth for an item's technical characteristics during the Sales and Production phases. Application logic often looks here first before falling back to the global `item_specifications`.
- **Production Integration**: These specifications are often pulled into `production_tasks` or `units` once a sale is confirmed, ensuring the manufacturing team builds according to the exact branch-sold spec.
- **Filtering**: Used for granular technical filtering in the store catalog (e.g., "Find all 60Hz units in this branch").

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| item_store_id | uuid | no | — | Foreign key to `item_stores.id`. |
| specification_id | uuid | no | — | Foreign key to `specifications.id`. |
| specification_name | text | no | — | Denormalized name (e.g., "Input Voltage"). |
| value | text | no | — | The actual value for this SKU. Examples of actual values include: `208`, `50`, `480Y/277`. |
| unit | text | no | '' | The technical unit (e.g., "VAC", "Hz"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| item_store_id | item_stores | id | cascade |
| specification_id | specifications | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Get the detailed technical datasheet for a branch SKU
SELECT specification_name, value, unit 
FROM item_store_specifications 
WHERE item_store_id = '<sku_uuid>';

-- List items in a store that match a specific voltage
SELECT ist.name 
FROM item_stores ist
JOIN item_store_specifications ispec ON ist.id = ispec.item_store_id
WHERE ist.store_id = '<uuid>' AND ispec.specification_name = 'Input Voltage' AND ispec.value = '208';
```

## Indexes
| Column(s) | Type | Purpose |
|-----------|------|---------|
| item_store_id | btree | Speeding up datasheet retrievals for specific branch items. |
| specification_id | btree | Reverse lookup: finding all SKUs with a specific attribute. |
