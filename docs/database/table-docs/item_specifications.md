# `item_specifications`

## Searchable Aliases
technical specs, product attributes, datasheet details, engineering specs, product dna

## Description
The `item_specifications` table stores the technical values assigned to an **Item Master (Blueprint)**. While the `specifications` table defines the "Question" (e.g., "Number Of Batteries"), this table provides the "Answer" (e.g., "1") for a specific product. These values are global; changing a value here updates the technical documentation for that product across the entire **Lyndom** (the current PostgreSQL ERP) system. Examples of actual values include `Number Of Batteries` (1), `TYPE` (Indoor), and `Battery Cabinet Quantity` (0).

## ⚠️ SQL-Critical Behaviors
- **Global Technical Profile**: This data defines the "Datasheet" for the product blueprint. It is used when generating submittal packages or technical manuals.
- **Unit Separation**: Values are stored as text, with a separate `unit` column to ensure mathematical consistency (e.g., Value: "277", Unit: "VAC").
- **Denormalized Names**: The `specification_name` is stored directly in this table to allow for fast, join-less retrieval of basic technical specs in search results.

## Columns

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | uuid | no | — | Primary key. |
| created_at | timestamptz | no | — | Creation timestamp. |
| updated_at | timestamptz | no | — | Last update timestamp. |
| item_id | uuid | no | — | Foreign key to `items.id`. |
| specification_id | uuid | no | — | Foreign key to `specifications.id`. |
| specification_name | text | no | — | Denormalized name (e.g., "Battery Cabinet"). |
| value | text | no | — | The actual value for this item. Examples of actual values include: `Indoor`, `1`, `N/A`. |
| unit | text | no | '' | The unit of measure for the value (e.g., "VAC", "Hz"). |

## Relationships

### References (FK Out)
| Column | → Table | → Column | On Delete |
|--------|---------|----------|-----------|
| item_id | items | id | cascade |
| specification_id | specifications | id | cascade |

### Referenced By (FK In)
- *None.*

## Common Query Patterns
```sql
-- Get the full technical datasheet for an item master record
SELECT specification_name, value, unit 
FROM item_specifications 
WHERE item_id = '<item_uuid>';

-- Find all items matching a specific technical criteria (e.g., 'Indoor' type)
SELECT i.name 
FROM items i
JOIN item_specifications ispec ON i.id = ispec.item_id
WHERE ispec.specification_name = 'TYPE' AND ispec.value = 'Indoor';
```

## Indexes
- *Uses default PK and FK constraints.*
